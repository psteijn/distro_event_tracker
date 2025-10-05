@echo off
echo ========================================
echo   Discord Event Tracker Bot Startup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ from https://python.org
    pause
    exit /b 1
)

echo Python found: 
python --version

REM Check if .env file exists
if not exist ".env" (
    echo.
    echo WARNING: .env file not found!
    echo Please copy env_example.txt to .env and add your Discord bot token
    echo.
    echo Creating .env file from template...
    copy env_example.txt .env
    echo.
    echo Please edit .env file and add your Discord bot token, then run this script again.
    pause
    exit /b 1
)

REM Check if virtual environment exists, create if not
if not exist "venv" (
    echo.
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update dependencies
echo.
echo Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

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

python main.py

REM If we get here, the bot stopped
echo.
echo Bot has stopped.
pause
