# Compatibility loader for the shared Home Infrastructure SSH transport.
Set-StrictMode -Version Latest
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$sharedRoot = if ($env:HOME_INFRASTRUCTURE_ROOT) { $env:HOME_INFRASTRUCTURE_ROOT } else { Join-Path (Split-Path -Parent $repositoryRoot) 'home-infrastructure' }
$transport = Join-Path $sharedRoot 'plugins\home-infrastructure\scripts\HomeInfrastructure.Transport.ps1'
if (-not (Test-Path -LiteralPath $transport)) {
    throw "Shared Home Infrastructure transport not found at '$transport'. Set HOME_INFRASTRUCTURE_ROOT or clone D:\dev\home-infrastructure."
}
. $transport
