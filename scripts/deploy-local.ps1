#Requires -Version 5.1
<#
.SYNOPSIS
  Build HollyWing Motor images locally and start the production stack.

.DESCRIPTION
  Uses docker-compose.yml + docker-compose.prod.yml. Builds every image from
  source on this host; nothing is pulled from GitHub or any other registry.
  Requires `.env` (copy from `.env.production.example`).
#>

param(
  [string]$Tag = "",
  [switch]$NoCache
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path (Join-Path $root ".env"))) {
  Write-Error "Missing .env in the repository root. Copy .env.production.example to .env and fill every CHANGE_ME value."
}

if ($Tag) { $env:IMAGE_TAG = $Tag }
if (-not $env:IMAGE_TAG) { $env:IMAGE_TAG = "local" }

$compose = @("-f", "docker-compose.yml", "-f", "docker-compose.prod.yml")
$upArgs = @("compose") + $compose + @("up", "-d", "--build", "--remove-orphans")
if ($NoCache) { $upArgs += "--no-cache" }

Write-Host "Building images locally (tag $env:IMAGE_TAG)..." -ForegroundColor Cyan
docker @upArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose @compose ps
Write-Host ""
Write-Host "Done. Frontend is on host port FRONTEND_PORT from .env (default 80)." -ForegroundColor Green
Write-Host "API is only reachable through nginx /api (not published on :8000)."
