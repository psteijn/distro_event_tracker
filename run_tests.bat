@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '%~dp0bootstrap-dev.ps1'; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; & '%~dp0.venv\Scripts\python.exe' -m pytest '%~dp0tests'"
exit /b %ERRORLEVEL%
