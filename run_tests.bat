@echo off
echo ========================================
echo   Discord Event Tracker Bot Tests
echo ========================================
echo.

set LOG_FILE=test_bot.log
call init.bat

python -m pytest tests/
set EXIT_CODE=%ERRORLEVEL%

REM Deactivate virtual environment
if exist "venv\Scripts\deactivate.bat" call venv\Scripts\deactivate.bat

if %EXIT_CODE% neq 0 (
    echo.
    echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    echo   TESTS FAILED! 
    echo   Check %LOG_FILE% for detailed error logs.
    echo xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    echo.
    exit /b %EXIT_CODE%
)

echo.
echo ✅ Tests completed successfully.
