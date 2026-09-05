#Requires -Version 5.1
<#
.SYNOPSIS
  One-command HollyWing Motor install/update for a Windows client PC.

  1. Clone or git pull from GitHub
  2. Create .env from .env.example if missing
  3. Start Docker Desktop if needed
  4. docker compose up -d --build (updates containers from source)
  5. Install desktop shortcut + Windows logon task
  6. Wait until healthy and open the app (optional)

.EXAMPLE
  # New PC or update - paste in PowerShell (any folder):
  irm https://raw.githubusercontent.com/Kimheang-code-IT/Rental_moto/main/scripts/install-client.ps1 | iex

  # Already cloned:
  .\scripts\install-client.ps1

  # Update code + Docker only (no shortcut reinstall):
  .\scripts\install-client.ps1 -SkipWindowsStartup
#>

param(
  [string]$RepoUrl = 'https://github.com/Kimheang-code-IT/Rental_moto.git',
  [string]$Branch = 'main',
  [string]$InstallDir = '',
  [switch]$SkipGitPull,
  [switch]$SkipWindowsStartup,
  [switch]$SkipOpenBrowser,
  [int]$TimeoutSeconds = 240
)

$ErrorActionPreference = 'Stop'

function Write-Step([string]$Message) {
  Write-Host ""
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-Command([string]$Name, [string]$Hint) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "$Name is not installed. $Hint"
  }
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
  if (Test-DockerReady) { return }

  $dockerDesktop = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
  if (-not (Test-Path -LiteralPath $dockerDesktop)) {
    throw "Docker Desktop was not found at: $dockerDesktop. Install Docker Desktop, start it once, then run this again."
  }

  Write-Step 'Starting Docker Desktop...'
  Start-Process -FilePath $dockerDesktop | Out-Null
  $deadline = (Get-Date).AddSeconds(150)
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 5
    if (Test-DockerReady) {
      Write-Host 'Docker engine is ready.' -ForegroundColor Green
      return
    }
    Write-Host '  Waiting for Docker engine...' -ForegroundColor DarkGray
  }
  throw 'Docker did not become ready within 150 seconds. Open Docker Desktop, wait until it is running, then run this again.'
}

function Get-FrontendPort([string]$RootPath) {
  $port = '80'
  $envFile = Join-Path $RootPath '.env'
  if (Test-Path -LiteralPath $envFile) {
    Get-Content -LiteralPath $envFile | ForEach-Object {
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

function Wait-StackHealthy([string]$LocalUrl, [int]$TimeoutSec) {
  $api = "$LocalUrl/api/v2/auth/setup-status"
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    try {
      $page = Invoke-WebRequest -Uri $LocalUrl -UseBasicParsing -TimeoutSec 5
      $probe = Invoke-WebRequest -Uri $api -UseBasicParsing -TimeoutSec 5
      if ($page.StatusCode -ge 200 -and $page.StatusCode -lt 400 -and $probe.StatusCode -eq 200) {
        return $true
      }
    } catch { }
    Start-Sleep -Seconds 3
  }
  return $false
}

# --- Preconditions ---------------------------------------------------------
Assert-Command git 'Install Git for Windows, then run this again.'
Assert-Command docker 'Install Docker Desktop, start it once, then run this again.'

# Resolve install root (works for local .\scripts\install-client.ps1 and irm | iex).
# Note: $PSScriptRoot is empty when the script is piped through Invoke-Expression.
$scriptRoot = ''
if ($PSScriptRoot) { $scriptRoot = [string]$PSScriptRoot }

$inRepo = $false
if ($scriptRoot) {
  $candidate = Split-Path -Parent $scriptRoot
  if ($candidate -and (Test-Path -LiteralPath (Join-Path $candidate 'docker-compose.yml'))) {
    $inRepo = $true
    if (-not $InstallDir) { $InstallDir = $candidate }
  }
}

# irm | iex: detect an existing checkout from the current directory.
if (-not $InstallDir) {
  $cwd = (Get-Location).Path
  if (Test-Path -LiteralPath (Join-Path $cwd 'docker-compose.yml')) {
    $InstallDir = $cwd
    $inRepo = $true
  }
}

if ($InstallDir) {
  $root = $InstallDir
} elseif ($inRepo -and $scriptRoot) {
  $root = Split-Path -Parent $scriptRoot
} else {
  $root = Join-Path $HOME 'Rental_moto'
}

Write-Host 'HollyWing Motor client install / update' -ForegroundColor Cyan
Write-Host "  Repo:   $RepoUrl ($Branch)"
Write-Host "  Folder: $root"

# --- Git clone or pull -----------------------------------------------------
$composePath = Join-Path $root 'docker-compose.yml'
if (-not (Test-Path -LiteralPath $composePath)) {
  Write-Step "Cloning $RepoUrl -> $root"
  $parent = Split-Path -Parent $root
  if ($parent -and -not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
  }
  git clone --branch $Branch --single-branch $RepoUrl $root
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} elseif (-not $SkipGitPull) {
  Write-Step "Updating from GitHub ($Branch)"
  git -C $root fetch origin $Branch
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  git -C $root checkout $Branch
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  git -C $root pull --ff-only origin $Branch
  if ($LASTEXITCODE -ne 0) {
    Write-Host 'git pull --ff-only failed. Resolve local changes, or re-run with a clean folder.' -ForegroundColor Red
    exit $LASTEXITCODE
  }
} else {
  Write-Host 'Skipping git pull (-SkipGitPull).' -ForegroundColor DarkGray
}

Set-Location -LiteralPath $root

# --- Env file --------------------------------------------------------------
$envFile = Join-Path $root '.env'
$envExample = Join-Path $root '.env.example'
if (-not (Test-Path -LiteralPath $envFile)) {
  if (-not (Test-Path -LiteralPath $envExample)) {
    throw ".env.example is missing in $root"
  }
  Copy-Item -LiteralPath $envExample -Destination $envFile
  Write-Host 'Created .env from .env.example (edit secrets later if needed).' -ForegroundColor Yellow
}

# --- Docker build / update -------------------------------------------------
Start-DockerDesktopIfNeeded

$env:IMAGE_TAG = 'local'
$env:PULL_POLICY = 'build'

Write-Step 'Building and starting Docker stack (this can take several minutes on first run)...'
docker compose -f docker-compose.yml up -d --build --pull missing
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# --- Windows shortcut + logon task -----------------------------------------
if (-not $SkipWindowsStartup) {
  $windowsInstaller = Join-Path $root 'scripts\windows\install-windows-startup.ps1'
  if (Test-Path -LiteralPath $windowsInstaller) {
    Write-Step 'Installing desktop shortcut and Windows logon startup...'
    & $windowsInstaller
    if ($LASTEXITCODE -ne 0) {
      Write-Host 'Windows startup install reported an error (app containers may still be running).' -ForegroundColor Yellow
    }
  } else {
    Write-Host "Windows installer not found at $windowsInstaller - skipped." -ForegroundColor Yellow
  }
}

# --- Wait + open -----------------------------------------------------------
$frontendPort = Get-FrontendPort $root
$localUrl = Get-LocalAppUrl $frontendPort

Write-Step "Waiting until the app is healthy at $localUrl ..."
$healthy = Wait-StackHealthy -LocalUrl $localUrl -TimeoutSec $TimeoutSeconds
if (-not $healthy) {
  Write-Host "Containers started, but the app was not healthy within ${TimeoutSeconds}s." -ForegroundColor Yellow
  Write-Host "Check: docker compose -f `"$root\docker-compose.yml`" ps"
  Write-Host "Logs:  docker compose -f `"$root\docker-compose.yml`" logs --tail 80 frontend api"
  exit 1
}

Write-Host ""
Write-Host 'HollyWing Motor is ready.' -ForegroundColor Green
Write-Host "  App:      $localUrl"
Write-Host "  API docs: http://localhost:8000/docs"
Write-Host "  Folder:   $root"
Write-Host "  Shortcut: HollyWing Motor (Desktop)"
Write-Host "  First visit: open /auth/setup to create the owner (email + password)."
Write-Host ""
Write-Host 'Later updates: run the same install command again (pulls GitHub + rebuilds Docker).' -ForegroundColor Cyan

if (-not $SkipOpenBrowser) {
  $launcher = Join-Path $root 'scripts\windows\start-hollywing.ps1'
  if (Test-Path -LiteralPath $launcher) {
    & $launcher -Quiet
  } else {
    Start-Process $localUrl
  }
}
