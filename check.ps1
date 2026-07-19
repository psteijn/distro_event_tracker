[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
& (Join-Path $repoRoot 'bootstrap-dev.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $repoRoot 'src'

& $python -m black --check src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m ruff check src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m mypy
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& (Join-Path $repoRoot '.venv\Scripts\lint-imports.exe')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m pytest --cov=distro_event_tracker --cov-report=term-missing tests
exit $LASTEXITCODE
