#!/bin/bash

# Discord Event Tracker Bot Startup Script for Windows (Git Bash/WSL)
echo "========================================"
echo "  Discord Event Tracker Bot Startup"
echo "========================================"
echo

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo "ERROR: Python is not installed or not in PATH"
    echo "Please install Python 3.7+ from https://python.org"
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Python found:"
python --version

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo
    echo "WARNING: .env file not found!"
    echo "Please copy env_example.txt to .env and add your Discord bot token"
    echo
    echo "Creating .env file from template..."
    cp env_example.txt .env
    echo
    echo "Please edit .env file and add your Discord bot token, then run this script again."
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo
    echo "Creating virtual environment..."
    python -m venv venv
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create virtual environment"
        read -p "Press Enter to exit..."
        exit 1
    fi
fi

# Activate virtual environment
echo
echo "Activating virtual environment..."
source venv/Scripts/activate

# Install/update dependencies
echo
echo "Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if Discord token is set
echo
echo "Checking Discord bot token..."
if grep -q "DISCORD_TOKEN=your_bot_token_here" .env; then
    echo "ERROR: Discord bot token not configured!"
    echo "Please edit .env file and replace 'your_bot_token_here' with your actual bot token"
    read -p "Press Enter to exit..."
    exit 1
fi

# Start the bot
echo
echo "========================================"
echo "  Starting Discord Event Tracker Bot"
echo "========================================"
echo
echo "Bot is starting... Press Ctrl+C to stop the bot"
echo

python main.py

# If we get here, the bot stopped
echo
echo "Bot has stopped."
read -p "Press Enter to exit..."
