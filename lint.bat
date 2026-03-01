@echo off
REM Run Black (format) and Ruff (lint) in fix mode.
call "%~dp0init.bat"
if errorlevel 1 exit /b 1

echo.
echo Installing lint tools if needed...
pip install -q -r requirements-dev.txt
if errorlevel 1 (
    echo ERROR: Install dev deps first: pip install -r requirements-dev.txt
    exit /b 1
)

echo.
echo --- Black (format) ---
python -m black .
if errorlevel 1 exit /b 1
echo Black done.

echo.
echo --- Ruff (lint fix) ---
python -m ruff check . --fix
if errorlevel 1 exit /b 1
echo Ruff done.
