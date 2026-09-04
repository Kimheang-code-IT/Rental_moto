@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "REPO_URL=https://github.com/Kimheang-code-IT/Rental_moto.git"
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
  echo This script must be run from the cloned Rental_moto project.
  exit /b 1
)

echo Updating code from GitHub...
git pull --ff-only

if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo Created .env from .env.example. Edit TELEGRAM_BOT_TOKEN if you need Telegram.
)

echo Building and starting from source (no app image pull)...
docker compose -f docker-compose.yml up -d --build --pull missing
if errorlevel 1 exit /b 1

docker compose -f docker-compose.yml ps
echo.
echo HollyWing Motor is starting on this computer.
echo   App:  http://localhost
echo   API:  http://localhost:8000/docs
echo   Login: admin@gmail.com / 123456
echo.
echo Logs: docker compose logs -f frontend api
endlocal
