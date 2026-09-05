[CmdletBinding()]
param([Parameter(Mandatory)][string]$Command)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'remote.ps1')
(Invoke-DistroAdmin -Command $Command).Stdout | Write-Host
