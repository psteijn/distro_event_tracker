@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '%~dp0bootstrap-dev.ps1'; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; Set-Location '%~dp0'; & '.\.venv\Scripts\python.exe' -m black src tests; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; & '.\.venv\Scripts\python.exe' -m ruff check src tests --fix"
exit /b %ERRORLEVEL%
