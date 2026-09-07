#Requires -Version 5.1
# iex-safe bootstrap (no param() block). Windows PowerShell 5.1 cannot
# `irm | iex` a script that starts with param().
#
# New PC:
#   irm https://raw.githubusercontent.com/Kimheang-code-IT/Rental_moto/main/scripts/bootstrap-install.ps1 | iex

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$url = 'https://raw.githubusercontent.com/Kimheang-code-IT/Rental_moto/main/scripts/install-client.ps1'
$dest = Join-Path $env:TEMP 'hollywing-install-client.ps1'
Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& $dest
