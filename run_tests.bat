@echo off
echo ========================================
echo   Discord Event Tracker Bot Tests
echo ========================================
echo.

call init.bat

python -m pytest tests/

echo.
echo Tests completed.
