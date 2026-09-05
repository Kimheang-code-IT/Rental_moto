#Requires -Version 5.1
<#
  Compatibility wrapper — prefer scripts\windows\start-hollywing.ps1
#>
& (Join-Path $PSScriptRoot 'windows\start-hollywing.ps1') @args
exit $LASTEXITCODE
