@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
if exist "install-client.cmd" (
  call "install-client.cmd"
  exit /b %ERRORLEVEL%
)
echo install-client.cmd is missing from the project folder.
echo Run these commands in cmd instead:
echo   git checkout main
echo   git pull origin main
echo   copy /Y .env.example .env
echo   docker compose -f docker-compose.yml up -d --build --pull missing
endlocal
exit /b 1
