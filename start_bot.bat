@echo off
echo ========================================
echo   Discord Event Tracker Bot Startup
echo ========================================
echo.

call init.bat

REM Check if Discord token is set
echo.
echo Checking Discord bot token...
findstr /C:"DISCORD_TOKEN=your_bot_token_here" .env >nul
if not errorlevel 1 (
    echo ERROR: Discord bot token not configured!
    echo Please edit .env file and replace 'your_bot_token_here' with your actual bot token
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
