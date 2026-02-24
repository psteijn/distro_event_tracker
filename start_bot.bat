@echo off
echo ========================================
echo   Discord Event Tracker Bot Startup
echo ========================================
echo.

call init.bat

REM Set default ENV_FILE if not set
if "%ENV_FILE%"=="" set ENV_FILE=.env

REM Check if Discord token is set
echo.
echo Checking Discord bot token in %ENV_FILE%...
findstr /C:"DISCORD_TOKEN=your_bot_token_here" %ENV_FILE% >nul
if not errorlevel 1 (
    echo ERROR: Discord bot token not configured!
    echo Please edit %ENV_FILE% file and replace 'your_bot_token_here' with your actual bot token
    pause
    exit /b 1
)

REM Start the bot
echo.
echo ========================================
echo   Starting Discord Event Tracker Bot
echo ========================================
echo.
echo Bot is starting... Press Ctrl+C to stop the bot
echo.

set PYTHONIOENCODING=utf-8
python main.py

REM If we get here, the bot stopped
echo.
echo Bot has stopped.
pause
