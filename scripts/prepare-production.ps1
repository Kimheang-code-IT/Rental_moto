#Requires -Version 5.1
<#
.SYNOPSIS
  Prepare HollyWing Motor for a clean production-ready local/prod start.

.DESCRIPTION
  - Resets PostgreSQL operational data (keeps users, roles, sequences, settings)
  - Clears local export files under /srv/data/exports
  - Removes local Python/Node/tooling caches

  Does NOT rewrite .env secrets. Fill .env.production.example manually before a real deploy.
#>

param(
  [switch]$SkipFiles,
  [switch]$SkipDbReset,
  [switch]$SkipCacheClean
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== HollyWing Motor production prepare ==" -ForegroundColor Cyan

if (-not $SkipDbReset) {
  Write-Host "Resetting operational data (keeping users, roles, sequences, settings)..." -ForegroundColor Yellow
  docker compose exec -T api python scripts/reset_db.py
}

if (-not $SkipFiles) {
  Write-Host "Clearing local export files..." -ForegroundColor Yellow
  docker compose exec -T api sh -c "rm -rf /srv/data/exports/* 2>/dev/null; echo Export files cleared"
}

if (-not $SkipCacheClean) {
  Write-Host "Cleaning local caches..." -ForegroundColor Yellow
  $paths = @(
    "tmp",
    "backend/.pytest_cache",
    "backend/.ruff_cache",
    "frontend/.nuxt",
    "frontend/.output",
    "frontend/.cache",
    ".ruff_cache",
    ".pytest_cache"
  )
  foreach ($path in $paths) {
    $full = Join-Path $root $path
    if (Test-Path $full) {
      Remove-Item -Recurse -Force $full
      Write-Host "  removed $path"
    }
  }
  Get-ChildItem -Path (Join-Path $root "backend") -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "Next:"
Write-Host "  1. Copy .env.production.example -> .env and set strong secrets"
Write-Host "  2. docker login ghcr.io"
Write-Host "  3. .\scripts\deploy-from-registry.ps1"
Write-Host "  4. Follow docs/PRODUCTION_CHECKLIST.md"
Write-Host "After reset, register the first administrator at /auth/setup (email + password)."
