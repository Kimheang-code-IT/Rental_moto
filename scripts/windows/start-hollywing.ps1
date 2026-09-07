#Requires -Version 5.1
<#
.SYNOPSIS
  HollyWing Motor launcher for Windows clients (desktop shortcut + logon task).

  - Starts Docker Desktop if needed
  - Starts docker compose only when the app is not already healthy
  - Waits for frontend + /api/v2/auth/setup-status
  - Opens Chrome/Edge in --app mode (desktop-style window)
  - Single-instance via named mutex; skips opening a second app window

.PARAMETER Quiet
  No interactive prompts; failures are written to a log file and the process exits.

.PARAMETER NoBrowser
  Start the stack only; do not open Chrome/Edge.

.PARAMETER TimeoutSeconds
  Maximum wait for the stack to become healthy (default 180).

.PARAMETER RetryDelaySeconds
  Delay between health probes (default 3).
#>

param(
  [switch]$Quiet,
  [switch]$NoBrowser,
  [int]$TimeoutSeconds = 180,
  [int]$RetryDelaySeconds = 3
)

$ErrorActionPreference = 'Stop'

$ScriptDir = $PSScriptRoot
$Root = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$EnvFile = Join-Path $Root '.env'
$LogDir = Join-Path $env:LOCALAPPDATA 'HollyWingMotor'
$LogFile = Join-Path $LogDir 'startup.log'
$ComposeFile = Join-Path $Root 'docker-compose.yml'

function Write-Log([string]$Message, [string]$Level = 'INFO') {
  try {
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
    $line = '{0:yyyy-MM-dd HH:mm:ss} [{1}] {2}' -f (Get-Date), $Level, $Message
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
  } catch { }
  if (-not $Quiet) {
    $color = switch ($Level) {
      'ERROR' { 'Red' }
      'WARN' { 'Yellow' }
      'OK' { 'Green' }
      default { 'Cyan' }
    }
    Write-Host $Message -ForegroundColor $color
  }
}

function Get-FrontendPort {
  $port = '80'
  if (Test-Path $EnvFile) {
    Get-Content -LiteralPath $EnvFile | ForEach-Object {
      if ($_ -match '^\s*FRONTEND_PORT\s*=\s*(.+?)\s*$') {
        $port = $Matches[1].Trim('"', "'")
      }
    }
  }
  if (-not $port) { $port = '80' }
  return $port
}

function Get-LocalAppUrl([string]$Port) {
  if ($Port -eq '80') { return 'http://localhost' }
  return "http://localhost:$Port"
}

function Test-UrlHealthy([string]$Url, [int]$TimeoutSec = 5) {
  try {
    $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
    return ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400)
  } catch {
    return $false
  }
}

function Test-StackHealthy([string]$LocalUrl) {
  $apiProbe = "$LocalUrl/api/v2/auth/setup-status"
  return (Test-UrlHealthy $LocalUrl) -and (Test-UrlHealthy $apiProbe)
}

function Wait-StackHealthy([string]$LocalUrl, [int]$TimeoutSec, [int]$DelaySec) {
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    if (Test-StackHealthy $LocalUrl) { return $true }
    Start-Sleep -Seconds $DelaySec
  }
  return $false
}

function Test-DockerReady {
  try {
    docker info --format '{{.ServerVersion}}' 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
  } catch {
    return $false
  }
}

function Start-DockerDesktopIfNeeded {
  if (Test-DockerReady) { return $true }

  $dockerDesktop = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
  if (-not (Test-Path $dockerDesktop)) {
    throw "Docker Desktop was not found at: $dockerDesktop"
  }

  Write-Log 'Starting Docker Desktop...'
  Start-Process -FilePath $dockerDesktop | Out-Null
  $deadline = (Get-Date).AddSeconds(150)
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 5
    if (Test-DockerReady) {
      Write-Log 'Docker engine is ready.' 'OK'
      return $true
    }
    Write-Log 'Waiting for Docker engine...'
  }
  throw 'Docker did not become ready within 150 seconds.'
}

function Start-ComposeStack {
  Set-Location -LiteralPath $Root
  Write-Log "Ensuring HollyWing Motor containers are running from $Root"

  $images = @()
  docker compose -f $ComposeFile config --images 2>$null | ForEach-Object {
    if ($_.Trim()) { $images += $_.Trim() }
  }
  $missing = @()
  foreach ($img in $images) {
    docker image inspect $img *> $null
    if ($LASTEXITCODE -ne 0) { $missing += $img }
  }

  if ($missing.Count -gt 0) {
    Write-Log 'Building missing images (first run can take several minutes)...' 'WARN'
    docker compose -f $ComposeFile up -d --build
  } else {
    # Avoid forced rebuilds from pull_policy: build on every launch.
    $env:PULL_POLICY = 'missing'
    docker compose -f $ComposeFile up -d
  }
  if ($LASTEXITCODE -ne 0) {
    throw "'docker compose up -d' failed (exit code $LASTEXITCODE)."
  }
}

function Find-BrowserExe {
  $chromeCandidates = @(
    "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
  )
  foreach ($path in $chromeCandidates) {
    if ($path -and (Test-Path -LiteralPath $path)) {
      return @{ Exe = $path; Name = 'chrome' }
    }
  }

  $edgeCandidates = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe"
  )
  foreach ($path in $edgeCandidates) {
    if ($path -and (Test-Path -LiteralPath $path)) {
      return @{ Exe = $path; Name = 'msedge' }
    }
  }
  return $null
}

function Test-AppWindowOpen([string]$Url) {
  try {
    $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -in @('chrome.exe', 'msedge.exe') -and $_.CommandLine }
    foreach ($p in $procs) {
      if ($p.CommandLine -like "*--app=$Url*") { return $true }
    }
  } catch { }
  return $false
}

function Open-HollyWingApp([string]$Url) {
  if (Test-AppWindowOpen $Url) {
    Write-Log "App window already open for $Url - skipping new browser window." 'OK'
    return
  }

  $browser = Find-BrowserExe
  if ($browser) {
    Write-Log "Opening HollyWing Motor in $($browser.Name) app mode: $Url" 'OK'
    Start-Process -FilePath $browser.Exe -ArgumentList @("--app=$Url")
    return
  }

  Write-Log "Chrome/Edge not found - opening default browser: $Url" 'WARN'
  Start-Process $Url
}

# --- Single-instance guard -------------------------------------------------
$mutex = $null
$ownedMutex = $false
try {
  $mutex = New-Object System.Threading.Mutex($false, 'Local\HollyWingMotorStart')
  $ownedMutex = $mutex.WaitOne(0)
  if (-not $ownedMutex) {
    Write-Log 'Another HollyWing Motor startup is already running - exiting.'
    exit 0
  }

  if (-not (Test-Path -LiteralPath $ComposeFile)) {
    throw "docker-compose.yml not found at $ComposeFile"
  }
  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker is not installed or not in PATH. Install Docker Desktop and try again.'
  }

  $frontendPort = Get-FrontendPort
  $localUrl = Get-LocalAppUrl $frontendPort

  if (Test-StackHealthy $localUrl) {
    Write-Log "Stack already healthy at $localUrl" 'OK'
    if (-not $NoBrowser) { Open-HollyWingApp $localUrl }
    exit 0
  }

  Start-DockerDesktopIfNeeded | Out-Null
  Start-ComposeStack

  Write-Log "Waiting for $localUrl and API (timeout ${TimeoutSeconds}s)..."
  $healthy = Wait-StackHealthy -LocalUrl $localUrl -TimeoutSec $TimeoutSeconds -DelaySec $RetryDelaySeconds
  if (-not $healthy) {
    throw "The app did not become healthy at $localUrl within ${TimeoutSeconds}s. Check: docker compose -f `"$ComposeFile`" ps"
  }

  Write-Log "HollyWing Motor is ready at $localUrl" 'OK'
  if (-not $NoBrowser) { Open-HollyWingApp $localUrl }
  exit 0
}
catch {
  $msg = $_.Exception.Message
  Write-Log "HollyWing Motor could not start: $msg" 'ERROR'
  if (-not $Quiet) {
    Write-Host ''
    Read-Host 'Press Enter to close this window'
  }
  exit 1
}
finally {
  if ($ownedMutex -and $mutex) {
    try { $mutex.ReleaseMutex() } catch { }
  }
  if ($mutex) { $mutex.Dispose() }
}
