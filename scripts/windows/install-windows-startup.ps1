#Requires -Version 5.1
<#
.SYNOPSIS
  One-time Windows client setup for HollyWing Motor.

  - Creates Desktop + Start Menu shortcut "HollyWing Motor"
  - Registers a hidden Task Scheduler task at user logon
  - Reminds / best-effort enables Docker Desktop start-at-login
  - Safe to run more than once (idempotent)

.EXAMPLE
  .\scripts\windows\install-windows-startup.ps1
  .\scripts\windows\install-windows-startup.ps1 -NoTask
  .\scripts\windows\install-windows-startup.ps1 -NoShortcut
#>

param(
  [switch]$NoTask,
  [switch]$NoShortcut,
  [switch]$NoStartMenu,
  [int]$LogonDelaySeconds = 45
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$ScriptDir = $PSScriptRoot
$Root = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$LogoPng = Join-Path $Root 'frontend\public\logo.png'
$IcoPath = Join-Path $ScriptDir 'hollywing.ico'
$Launcher = Join-Path $ScriptDir 'start-hollywing.ps1'
$TaskName = 'HollyWing Motor'
$ShortcutName = 'HollyWing Motor.lnk'
$PowerShellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

if (-not (Test-Path -LiteralPath (Join-Path $Root 'docker-compose.yml'))) {
  throw "docker-compose.yml not found under $Root"
}
if (-not (Test-Path -LiteralPath $LogoPng)) { throw "Logo not found: $LogoPng" }
if (-not (Test-Path -LiteralPath $Launcher)) { throw "Launcher not found: $Launcher" }

function ConvertTo-BmpIcoEntry {
  param([System.Drawing.Bitmap]$Bitmap, [int]$Size)

  $rect = New-Object System.Drawing.Rectangle 0, 0, $Size, $Size
  $data = $Bitmap.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly,
                           [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
  try {
    $stride = $data.Stride
    $pixels = New-Object byte[] ($Size * $Size * 4)
    $row = New-Object byte[] $stride
    $ptr = $data.Scan0
    for ($y = 0; $y -lt $Size; $y++) {
      [System.Runtime.InteropServices.Marshal]::Copy(
        [IntPtr]::Add($ptr, $y * $stride), $row, 0, $stride)
      [Array]::Copy($row, 0, $pixels, ($Size - 1 - $y) * $Size * 4, $Size * 4)
    }
  } finally {
    $Bitmap.UnlockBits($data)
  }

  $ms = New-Object System.IO.MemoryStream
  $bw = New-Object System.IO.BinaryWriter $ms
  $bw.Write([UInt32]40)
  $bw.Write([Int32]$Size)
  $bw.Write([Int32]($Size * 2))
  $bw.Write([UInt16]1)
  $bw.Write([UInt16]32)
  $bw.Write([UInt32]0)
  $bw.Write([UInt32]($Size * $Size * 4))
  $bw.Write([Int32]0); $bw.Write([Int32]0); $bw.Write([UInt32]0); $bw.Write([UInt32]0)
  $bw.Write($pixels)
  $maskRowBytes = [int]([Math]::Ceiling($Size / 32.0)) * 4
  $bw.Write((New-Object byte[] ($maskRowBytes * $Size)))
  $bw.Flush()
  $bytes = $ms.ToArray()
  $bw.Dispose(); $ms.Dispose()
  , $bytes
}

function ConvertTo-Ico {
  param([string]$SourcePng, [string]$DestinationIco)

  $src = [System.Drawing.Image]::FromFile($SourcePng)
  try {
    $streams = @()
    $meta = @()
    foreach ($size in 16, 32, 48, 256) {
      $square = New-Object System.Drawing.Bitmap $size, $size
      $g = [System.Drawing.Graphics]::FromImage($square)
      $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
      $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
      $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
      $g.Clear([System.Drawing.Color]::Transparent)
      $scale = $size / [Math]::Max($src.Width, $src.Height)
      $w = [int][Math]::Round($src.Width * $scale)
      $h = [int][Math]::Round($src.Height * $scale)
      $x = [int][Math]::Floor(($size - $w) / 2)
      $y = [int][Math]::Floor(($size - $h) / 2)
      $g.DrawImage($src, $x, $y, $w, $h)
      $g.Dispose()

      if ($size -le 48) {
        $entry = ConvertTo-BmpIcoEntry $square $size
        $streams += , [byte[]]$entry
      } else {
        $ms = New-Object System.IO.MemoryStream
        $square.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
        $streams += , $ms.ToArray()
      }
      $meta += , @($size, $size, $streams[$streams.Count - 1].Length)
      $square.Dispose()
    }

    $ms = New-Object System.IO.MemoryStream
    $bw = New-Object System.IO.BinaryWriter $ms
    $bw.Write([UInt16]0)
    $bw.Write([UInt16]1)
    $bw.Write([UInt16]$meta.Count)
    $offset = 6 + 16 * $meta.Count
    for ($i = 0; $i -lt $meta.Count; $i++) {
      $s = $meta[$i][0]
      $bw.Write([Byte]($(if ($s -ge 256) { 0 } else { $s })))
      $bw.Write([Byte]($(if ($s -ge 256) { 0 } else { $s })))
      $bw.Write([Byte]0)
      $bw.Write([Byte]0)
      $bw.Write([UInt16]1)
      $bw.Write([UInt16]32)
      $bw.Write([UInt32]$meta[$i][2])
      $bw.Write([UInt32]$offset)
      $offset += $meta[$i][2]
    }
    foreach ($bytes in $streams) { $bw.Write($bytes) }
    $bw.Flush()
    [System.IO.File]::WriteAllBytes($DestinationIco, $ms.ToArray())
    $bw.Dispose(); $ms.Dispose()
  } finally {
    $src.Dispose()
  }
}

function New-HollywingShortcut {
  param([string]$Path)

  $shell = New-Object -ComObject WScript.Shell
  $lnk = $shell.CreateShortcut($Path)
  $lnk.TargetPath = $PowerShellExe
  # Hidden PowerShell window - client never sees a console.
  $lnk.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Launcher`" -Quiet"
  $lnk.WorkingDirectory = $Root
  $lnk.IconLocation = "$IcoPath,0"
  $lnk.WindowStyle = 7
  $lnk.Description = 'Start HollyWing Motor (Docker stack + app window)'
  $lnk.Save()
  Write-Host "Shortcut created: $Path" -ForegroundColor Green
}

function Enable-DockerDesktopAutoStart {
  # Best-effort: Docker Desktop JSON settings differ by version. Documented fallback always applies.
  $candidates = @(
    (Join-Path $env:APPDATA 'Docker\settings-store.json'),
    (Join-Path $env:APPDATA 'Docker\settings.json')
  )
  foreach ($path in $candidates) {
    if (-not (Test-Path -LiteralPath $path)) { continue }
    try {
      $raw = Get-Content -LiteralPath $path -Raw -Encoding UTF8
      $json = $raw | ConvertFrom-Json
      $changed = $false
      if ($null -ne $json.autoStart -and $json.autoStart -ne $true) {
        $json.autoStart = $true
        $changed = $true
      }
      if ($null -ne $json.openAtLogin -and $json.openAtLogin -ne $true) {
        $json.openAtLogin = $true
        $changed = $true
      }
      # Newer settings-store uses nested keys as string values.
      if ($json.PSObject.Properties.Name -contains 'AutoStart') {
        if ([string]$json.AutoStart -ne 'true') { $json.AutoStart = 'true'; $changed = $true }
      }
      if ($changed) {
        $json | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $path -Encoding UTF8
        Write-Host "Enabled Docker Desktop auto-start in: $path" -ForegroundColor Green
        return
      }
    } catch {
      Write-Host "Could not update Docker Desktop settings at $path (safe to ignore)." -ForegroundColor DarkGray
    }
  }
  Write-Host "Enable Docker Desktop auto-start manually: Docker Desktop -> Settings -> General -> Start Docker Desktop when you log in." -ForegroundColor Yellow
}

function Register-LogonTask {
  $arg = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Launcher`" -Quiet"
  $action = New-ScheduledTaskAction -Execute $PowerShellExe -Argument $arg -WorkingDirectory $Root
  $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
  # Delay so Docker Desktop can initialize after Windows logon.
  try { $trigger.Delay = "PT${LogonDelaySeconds}S" } catch { }

  $settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
    -MultipleInstances IgnoreNew `
    -Hidden

  $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

  Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description 'Starts HollyWing Motor containers after logon and opens the app when healthy.' `
    -Force | Out-Null

  Write-Host "Scheduled task registered: $TaskName (At logon, +${LogonDelaySeconds}s delay, hidden)" -ForegroundColor Green
}

Write-Host "HollyWing Motor Windows setup" -ForegroundColor Cyan
Write-Host "  Project: $Root"

Write-Host "Generating icon..." -ForegroundColor Cyan
ConvertTo-Ico -SourcePng $LogoPng -DestinationIco $IcoPath

# Also keep a copy next to legacy scripts for older shortcuts.
$legacyIco = Join-Path (Split-Path -Parent $ScriptDir) 'hollywing.ico'
Copy-Item -LiteralPath $IcoPath -Destination $legacyIco -Force

if (-not $NoShortcut) {
  $desktop = [Environment]::GetFolderPath('Desktop')
  $desktopLnk = Join-Path $desktop $ShortcutName
  New-HollywingShortcut -Path $desktopLnk

  if (-not $NoStartMenu) {
    $startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\$ShortcutName"
    New-HollywingShortcut -Path $startMenu
  }

  # Remove older short-name shortcuts if present.
  foreach ($legacy in @(
      (Join-Path $desktop 'hollywing.lnk'),
      (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\hollywing.lnk')
    )) {
    if (Test-Path -LiteralPath $legacy) {
      Remove-Item -LiteralPath $legacy -Force -ErrorAction SilentlyContinue
    }
  }
}

if (-not $NoTask) {
  Register-LogonTask
}

Enable-DockerDesktopAutoStart

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "  Desktop shortcut: HollyWing Motor"
if (-not $NoTask) {
  Write-Host "  Logon task:       $TaskName"
}
Write-Host "  Launcher:         $Launcher"
Write-Host "  Startup log:      $env:LOCALAPPDATA\HollyWingMotor\startup.log"
Write-Host ""
Write-Host "Client usage: double-click HollyWing Motor - no Docker/CMD commands needed." -ForegroundColor Cyan
Write-Host "Uninstall:    .\scripts\windows\uninstall-windows-startup.ps1"
