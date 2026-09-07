@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "IMAGE_TAG=local"
set "PULL_POLICY=build"

where git >nul 2>&1
if errorlevel 1 (
  echo Git is not installed. Install Git, then run this again.
  exit /b 1
)
where docker >nul 2>&1
if errorlevel 1 (
  echo Docker is not installed. Install Docker Desktop, start it, then run this again.
  exit /b 1
)

if not exist "docker-compose.yml" (
  echo Run this from the Rental_moto folder.
  exit /b 1
)

echo Updating code from GitHub...
git pull origin main
if errorlevel 1 (
  echo git pull failed. Continuing with the files already on this computer.
)

if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo Created .env from .env.example.
)

echo Building from source (this computer, no GitHub app image pull)...
docker compose -f docker-compose.yml up -d --build --pull missing
if errorlevel 1 exit /b 1

docker compose -f docker-compose.yml ps
echo.
echo HollyWing Motor is starting.
echo   App:   http://localhost
echo   API:   http://localhost:8000/docs
echo   Login: admin@gmail.com / 123456
echo.
echo Logs: docker compose logs -f frontend api
endlocal
