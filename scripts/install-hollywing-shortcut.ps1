#Requires -Version 5.1
<#
.SYNOPSIS
  Installs the one-click "HollyWing Motor" shortcut (Desktop + Start Menu).

  - Converts frontend/public/logo.png into scripts/hollywing.ico (16/32/48/256)
    using .NET System.Drawing — no extra downloads or npm dependencies.
  - Creates the shortcut targeting scripts/start-hollywing.ps1.

.EXAMPLE
  .\scripts\install-hollywing-shortcut.ps1
  .\scripts\install-hollywing-shortcut.ps1 -NoStartMenu
#>

param(
  [switch]$NoStartMenu
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

$Root = Split-Path -Parent $PSScriptRoot
$LogoPng = Join-Path $Root "frontend\public\logo.png"
$IcoPath = Join-Path $PSScriptRoot "hollywing.ico"
$Launcher = Join-Path $PSScriptRoot "start-hollywing.ps1"

if (-not (Test-Path $LogoPng)) { throw "Logo not found: $LogoPng" }
if (-not (Test-Path $Launcher)) { throw "Launcher not found: $Launcher" }

# --- Convert logo.png -> hollywing.ico (PNG centered on a transparent square,
#     stored as classic BMP entries for 16/32/48 and a PNG entry for 256). ----
function ConvertTo-Ico {
  param([string]$SourcePng, [string]$DestinationIco)

  $src = [System.Drawing.Image]::FromFile($SourcePng)
  try {
    $streams = @()   # raw image bytes per entry
    $meta   = @()    # width, height, byte count

    foreach ($size in 16, 32, 48, 256) {
      $square = New-Object System.Drawing.Bitmap $size, $size
      $g = [System.Drawing.Graphics]::FromImage($square)
      $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
      $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
      $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
      $g.Clear([System.Drawing.Color]::Transparent)
      # Fit the (non-square) logo inside the square, preserving aspect ratio.
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
        $streams += ,$ms.ToArray()
      }
      $meta += ,@($size, $size, $streams[$streams.Count - 1].Length)
      $square.Dispose()
    }

    # ICO container: ICONDIR + ICONDIRENTRY array + image data.
    $ms = New-Object System.IO.MemoryStream
    $bw = New-Object System.IO.BinaryWriter $ms
    $bw.Write([UInt16]0)      # reserved
    $bw.Write([UInt16]1)      # type: icon
    $bw.Write([UInt16]$meta.Count)
    $offset = 6 + 16 * $meta.Count
    for ($i = 0; $i -lt $meta.Count; $i++) {
      $s = $meta[$i][0]
      $bw.Write([Byte]($(if ($s -ge 256) { 0 } else { $s })))  # width (0 = 256)
      $bw.Write([Byte]($(if ($s -ge 256) { 0 } else { $s })))  # height (0 = 256)
      $bw.Write([Byte]0)        # palette count
      $bw.Write([Byte]0)        # reserved
      $bw.Write([UInt16]1)      # color planes
      $bw.Write([UInt16]32)     # bits per pixel
      $bw.Write([UInt32]$meta[$i][2])   # bytes in resource
      $bw.Write([UInt32]$offset)        # image offset
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

# Encode a 32bpp bitmap as a bottom-up BGRA BMP frame + empty AND mask.
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
      # ICO BMP frames are bottom-up; the source row $y becomes row $Size-1-$y.
      [Array]::Copy($row, 0, $pixels, ($Size - 1 - $y) * $Size * 4, $Size * 4)
    }
  } finally {
    $Bitmap.UnlockBits($data)
  }

  $ms = New-Object System.IO.MemoryStream
  $bw = New-Object System.IO.BinaryWriter $ms
  # BITMAPINFOHEADER (biHeight is doubled for ICO frames: pixels + AND mask).
  $bw.Write([UInt32]40)                 # biSize
  $bw.Write([Int32]$Size)               # biWidth
  $bw.Write([Int32]($Size * 2))         # biHeight
  $bw.Write([UInt16]1)                  # biPlanes
  $bw.Write([UInt16]32)                 # biBitCount
  $bw.Write([UInt32]0)                  # biCompression (BI_RGB)
  $bw.Write([UInt32]($Size * $Size * 4))# biSizeImage
  $bw.Write([Int32]0); $bw.Write([Int32]0); $bw.Write([UInt32]0); $bw.Write([UInt32]0)
  $bw.Write($pixels)
  # AND mask: 1bpp, rows padded to 32 bits, all zero (alpha handles transparency).
  $maskRowBytes = [int]([Math]::Ceiling($Size / 32.0)) * 4
  $bw.Write((New-Object byte[] ($maskRowBytes * $Size)))
  $bw.Flush()
  $bytes = $ms.ToArray()
  $bw.Dispose(); $ms.Dispose()
  # Leading comma so the pipeline returns the byte[] intact (not enumerated).
  , $bytes
}

Write-Host "Generating $IcoPath from frontend\public\logo.png ..." -ForegroundColor Cyan
ConvertTo-Ico -SourcePng $LogoPng -DestinationIco $IcoPath
Write-Host "Icon written: $IcoPath" -ForegroundColor Green

# --- Create the shortcut(s) ------------------------------------------------
$shell = New-Object -ComObject WScript.Shell

function New-HollywingShortcut {
  param([string]$Path)
  $lnk = $shell.CreateShortcut($Path)
  $lnk.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
  $lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Launcher`""
  $lnk.WorkingDirectory = $Root
  $lnk.IconLocation = "$IcoPath,0"
  # 7 = minimized: progress is visible in the taskbar while Docker starts,
  # and the browser takes over once the app answers.
  $lnk.WindowStyle = 7
  $lnk.Description = "Start HollyWing Motor (Docker stack + browser)"
  $lnk.Save()
  Write-Host "Shortcut created: $Path" -ForegroundColor Green
}

$desktop = [Environment]::GetFolderPath("Desktop")
$desktopLnk = Join-Path $desktop "HollyWing Motor.lnk"
New-HollywingShortcut -Path $desktopLnk

if (-not $NoStartMenu) {
  $startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\HollyWing Motor.lnk"
  New-HollywingShortcut -Path $startMenu
}

Write-Host ""
Write-Host "Done. Double-click the shortcut to start HollyWing Motor." -ForegroundColor Cyan
Write-Host "Desktop shortcut: $desktopLnk"
