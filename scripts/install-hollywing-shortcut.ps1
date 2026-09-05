#Requires -Version 5.1
<#
  Compatibility wrapper — prefer scripts\windows\install-windows-startup.ps1

  Creates the HollyWing Motor desktop shortcut (and optional Start Menu entry).
  For full client setup (shortcut + logon task), run install-windows-startup.ps1.
#>
param(
  [switch]$NoStartMenu
)

$installer = Join-Path $PSScriptRoot 'windows\install-windows-startup.ps1'
$argsList = @('-NoTask')
if ($NoStartMenu) { $argsList += '-NoStartMenu' }
& $installer @argsList
exit $LASTEXITCODE
