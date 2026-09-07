# Start the full HollyWing Motor stack in Docker (build + detach).
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$FrontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { '80' }
Write-Host ""
Write-Host "HollyWing Motor is starting."
Write-Host "  Frontend (nginx): http://localhost:$FrontendPort"
Write-Host "  API:              http://localhost:8000/docs"
Write-Host ""
Write-Host "Check status: docker compose ps"
Write-Host "View logs:    docker compose logs -f frontend api"
