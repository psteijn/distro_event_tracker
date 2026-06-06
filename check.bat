@echo off
call "%~dp0init.bat"
if errorlevel 1 exit /b 1

python -m pip install -q -r requirements-dev.txt
if errorlevel 1 exit /b 1
python -m black --check src tests
if errorlevel 1 exit /b 1
python -m ruff check src tests
if errorlevel 1 exit /b 1
python -m mypy
if errorlevel 1 exit /b 1
set PYTHONPATH=%~dp0src
lint-imports
if errorlevel 1 exit /b 1
python -m pytest --cov=distro_event_tracker --cov-report=term-missing tests
exit /b %ERRORLEVEL%
