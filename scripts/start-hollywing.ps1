#Requires -Version 5.1
<#
.SYNOPSIS
  One-click HollyWing Motor launcher (used by the "HollyWing Motor" desktop shortcut).

  1. Starts Docker Desktop if it is not running
  2. Starts the full stack from the repository root (builds only when images are missing)
  3. Waits until the frontend answers
  4. Opens the default browser at the app URL

  Run directly or via the shortcut installed by scripts/install-hollywing-shortcut.ps1.
#>

$ErrorActionPreference = 'Stop'

function Wait-KeyPress {
  # Keep the console window open on failure so a double-click launch does not vanish.
  Write-Host ""
  Read-Host "Press Enter to close this window"
}

try {
  # --- 0. Resolve repository root ------------------------------------------
  $Root = Split-Path -Parent $PSScriptRoot
  $EnvFile = Join-Path $Root ".env"

  # --- 1. Docker must be installed and the daemon running -------------------
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed or not in PATH. Install Docker Desktop and try again."
  }

  $dockerReady = $false
  try {
    docker info --format '{{.ServerVersion}}' | Out-Null
    $dockerReady = ($LASTEXITCODE -eq 0)
  } catch { $dockerReady = $false }

  if (-not $dockerReady) {
    $dockerDesktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dockerDesktop)) {
      throw "Docker daemon is not running and Docker Desktop was not found at: $dockerDesktop`nStart Docker Desktop manually and try again."
    }
    Write-Host "Starting Docker Desktop..." -ForegroundColor Cyan
    Start-Process $dockerDesktop | Out-Null
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline) {
      Start-Sleep -Seconds 5
      docker info --format '{{.ServerVersion}}' | Out-Null
      if ($LASTEXITCODE -eq 0) { $dockerReady = $true; break }
      Write-Host "  Waiting for Docker engine..." -ForegroundColor DarkGray
    }
    if (-not $dockerReady) {
      throw "Docker did not become ready within 120 seconds. Open Docker Desktop, wait for it to finish starting, then click the shortcut again."
    }
    Write-Host "Docker is ready." -ForegroundColor Green
  }

  # --- 2. Start the stack from the repository root --------------------------
  Set-Location $Root
  Write-Host "Starting HollyWing Motor from $Root ..." -ForegroundColor Cyan

  # Rebuild only when a compose image is missing; otherwise a plain "up -d"
  # (re)starts existing containers without an unnecessary rebuild.
  $images = @()
  docker compose config --images 2>$null | ForEach-Object { if ($_.Trim()) { $images += $_.Trim() } }
  $missing = @()
  foreach ($img in $images) {
    docker image inspect $img *> $null
    if ($LASTEXITCODE -ne 0) { $missing += $img }
  }

  if ($missing.Count -gt 0) {
    Write-Host "Building missing images (first run can take several minutes)..." -ForegroundColor Yellow
    docker compose up -d --build
  } else {
    # docker-compose.yml sets pull_policy: build by default, which would rebuild
    # on every "up". All images exist, so relax the policy for this start.
    $env:PULL_POLICY = 'missing'
    docker compose up -d
  }
  if ($LASTEXITCODE -ne 0) { throw "'docker compose up -d' failed (exit code $LASTEXITCODE). See the messages above." }

  # --- 3. Frontend URL: this PC's Wi-Fi / LAN IP so phones on the same
  #     network can open the same address. Docker already binds 0.0.0.0.
  $frontendPort = "80"
  if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
      if ($_ -match '^\s*FRONTEND_PORT\s*=\s*(.+?)\s*$') { $frontendPort = $Matches[1].Trim('"', "'") }
    }
  }

  function Get-LanIPv4 {
    $wifi = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
      Where-Object {
        $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and
        $_.PrefixOrigin -ne 'WellKnown' -and
        $_.InterfaceAlias -match 'Wi-?Fi|Wireless|WLAN'
      })
    if ($wifi.Count -gt 0) { return $wifi[0].IPAddress }

    $lan = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
      Where-Object {
        $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and
        $_.PrefixOrigin -ne 'WellKnown' -and
        (
          $_.IPAddress -match '^192\.168\.' -or
          $_.IPAddress -match '^10\.' -or
          $_.IPAddress -match '^172\.(1[6-9]|2[0-9]|3[0-1])\.'
        )
      })
    if ($lan.Count -gt 0) { return $lan[0].IPAddress }
    return $null
  }

  $lanIp = Get-LanIPv4
  $localUrl = if ($frontendPort -eq '80') { 'http://localhost' } else { "http://localhost:$frontendPort" }
  $appUrl = if ($lanIp) {
    if ($frontendPort -eq '80') { "http://$lanIp" } else { "http://$lanIp`:$frontendPort" }
  } else {
    $localUrl
  }

  # Allow other devices on this Wi-Fi to reach the published frontend port.
  # Best-effort: skipped when this window is not elevated.
  try {
    $ruleName = "HollyWing Motor (TCP $frontendPort)"
    $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if (-not $existing) {
      New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $frontendPort -Profile Private -ErrorAction Stop | Out-Null
      Write-Host "Opened Windows Firewall for port $frontendPort (Private network)." -ForegroundColor Green
    }
  } catch {
    Write-Host "Could not add a firewall rule automatically. If phones cannot open the app, allow TCP $frontendPort inbound in Windows Firewall." -ForegroundColor Yellow
  }

  # --- 4. Wait until frontend AND API (via nginx /api) answer ----------------
  # Opening the browser while the API is still migrating/seeding causes 502
  # toasts and wrongly sends first-run users to the Login page.
  $apiProbe = "$localUrl/api/v2/auth/setup-status"
  Write-Host "Waiting for $localUrl and API at $apiProbe ..." -ForegroundColor Cyan
  $deadline = (Get-Date).AddSeconds(180)
  $healthy = $false
  while ((Get-Date) -lt $deadline) {
    try {
      $page = Invoke-WebRequest -Uri $localUrl -UseBasicParsing -TimeoutSec 5
      $api = Invoke-WebRequest -Uri $apiProbe -UseBasicParsing -TimeoutSec 5
      if ($page.StatusCode -ge 200 -and $page.StatusCode -lt 400 -and $api.StatusCode -eq 200) {
        $healthy = $true
        break
      }
    } catch { }
    Start-Sleep -Seconds 3
  }
  if (-not $healthy) {
    throw "The app/API did not answer at $localUrl within 3 minutes. Run 'docker compose ps' and 'docker compose logs frontend api' to check the stack."
  }

  # --- 5. Open the LAN URL so this PC and other Wi-Fi users share one address
  Write-Host "HollyWing Motor is running." -ForegroundColor Green
  Write-Host "  This PC:     $localUrl"
  Write-Host "  Wi-Fi share: $appUrl"
  Write-Host "Other phones/PCs on the same Wi-Fi should open: $appUrl" -ForegroundColor Cyan
  Start-Process $appUrl
} catch {
  Write-Host ""
  Write-Host "HollyWing Motor could not start: $($_.Exception.Message)" -ForegroundColor Red
  Wait-KeyPress
  exit 1
}
