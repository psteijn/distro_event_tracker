[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    & python -m venv (Join-Path $repoRoot '.venv')
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to create .venv.'
    }
}

& $python -m pip install --disable-pip-version-check -q -e "$repoRoot[dev]"
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to install development dependencies.'
}

Write-Host "Development environment ready: $python"
