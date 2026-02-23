#!/bin/bash

# Discord Event Tracker Bot Startup Script for Windows (Git Bash/WSL)
echo "========================================"
echo "  Discord Event Tracker Bot Startup"
echo "========================================"
echo

source "${BASH_SOURCE[0]%/*}/init.sh"

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
