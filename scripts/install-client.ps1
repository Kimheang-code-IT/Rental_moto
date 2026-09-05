#Requires -Version 5.1
<#
.SYNOPSIS
  Clone HollyWing Motor from GitHub and build it on this computer (no GHCR image pull).

.EXAMPLE
  # On a new client PC, from any folder:
  irm https://raw.githubusercontent.com/Kimheang-code-IT/Rental_moto/main/scripts/install-client.ps1 | iex

  # Or after cloning:
  .\scripts\install-client.ps1
#>

param(
  [string]$RepoUrl = "https://github.com/Kimheang-code-IT/Rental_moto.git",
  [string]$InstallDir = "",
  [switch]$SkipGitPull
)

$ErrorActionPreference = "Stop"

function Assert-Command($Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    Write-Error "$Name is not installed. Install Git and Docker Desktop, then run this script again."
  }
}

Assert-Command git
Assert-Command docker

$inRepo = Test-Path (Join-Path $PSScriptRoot "..\docker-compose.yml")
if ($InstallDir) {
  $root = $InstallDir
} elseif ($inRepo) {
  $root = Split-Path -Parent $PSScriptRoot
} else {
  $root = Join-Path $HOME "Rental_moto"
}

if (-not (Test-Path (Join-Path $root "docker-compose.yml"))) {
  Write-Host "Cloning $RepoUrl -> $root" -ForegroundColor Cyan
  git clone $RepoUrl $root
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} elseif (-not $SkipGitPull) {
  Write-Host "Updating $root" -ForegroundColor Cyan
  git -C $root pull --ff-only
}

Set-Location $root

if (-not (Test-Path (Join-Path $root ".env"))) {
  Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env")
  Write-Host "Created .env from .env.example. Edit TELEGRAM_BOT_TOKEN if you need Telegram." -ForegroundColor Yellow
}

$env:IMAGE_TAG = "local"
$env:PULL_POLICY = "build"

Write-Host "Building and starting from source (no app image pull)..." -ForegroundColor Cyan
docker compose -f docker-compose.yml up -d --build --pull missing
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$frontendPort = "80"
Get-Content (Join-Path $root ".env") | ForEach-Object {
  if ($_ -match '^\s*FRONTEND_PORT\s*=\s*(.+)\s*$') { $frontendPort = $Matches[1].Trim() }
}

docker compose -f docker-compose.yml ps
Write-Host ""
Write-Host "HollyWing Motor is starting on this computer." -ForegroundColor Green
Write-Host "  App:  http://localhost:$frontendPort"
Write-Host "  API:  http://localhost:8000/docs"
Write-Host "  First visit: register the system owner at /auth/setup (email + password)."
Write-Host ""
Write-Host "Logs: docker compose logs -f frontend api"
