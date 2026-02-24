
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

REM Set default ENV_FILE if not set
if "%ENV_FILE%"=="" set ENV_FILE=.env

REM Check if environment file exists
if not exist "%ENV_FILE%" (
    echo.
    echo WARNING: %ENV_FILE% not found!
    if "%ENV_FILE%"==".env" (
        echo Please copy env_example.txt to .env and add your Discord bot token
        echo.
        echo Creating .env file from template...
        copy env_example.txt .env
        echo.
        echo Please edit .env file and add your Discord bot token, then run this script again.
    ) else (
        echo Please ensure %ENV_FILE% exists with your configuration.
    )
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
