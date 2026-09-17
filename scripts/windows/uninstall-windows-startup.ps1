#Requires -Version 5.1
<#
.SYNOPSIS
  Removes HollyWing Motor Windows startup integration only.

  - Removes the Task Scheduler task created by install-windows-startup.ps1
  - Removes the Desktop / Start Menu "HollyWing Motor" shortcuts
  - Does NOT remove Docker, project files, databases, or Docker volumes

.EXAMPLE
  .\scripts\windows\uninstall-windows-startup.ps1
#>

$ErrorActionPreference = 'Stop'

$TaskName = 'HollyWing Motor'
$ShortcutName = 'HollyWing Motor.lnk'
$removed = @()

# --- Scheduled task --------------------------------------------------------
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
  $removed += "Scheduled task: $TaskName"
  Write-Host "Removed scheduled task: $TaskName" -ForegroundColor Green
} else {
  Write-Host "Scheduled task not found: $TaskName" -ForegroundColor DarkGray
}

# --- Shortcuts created by this project -------------------------------------
$shortcutPaths = @(
  (Join-Path ([Environment]::GetFolderPath('Desktop')) $ShortcutName),
  (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\$ShortcutName"),
  (Join-Path ([Environment]::GetFolderPath('Desktop')) 'hollywing.lnk'),
  (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\hollywing.lnk')
)

foreach ($path in $shortcutPaths) {
  if (Test-Path -LiteralPath $path) {
    Remove-Item -LiteralPath $path -Force
    $removed += "Shortcut: $path"
    Write-Host "Removed shortcut: $path" -ForegroundColor Green
  }
}

Write-Host ""
if ($removed.Count -eq 0) {
  Write-Host "Nothing to remove. Startup integration was not installed (or already uninstalled)." -ForegroundColor Yellow
} else {
  Write-Host "Uninstall complete. Docker and project data were left untouched." -ForegroundColor Cyan
}
Write-Host "Containers (if running) keep their restart policy; stop them with: docker compose down"
