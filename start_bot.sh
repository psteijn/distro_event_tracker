#!/bin/bash

# Discord Event Tracker Bot Startup Script for Windows (Git Bash/WSL)
echo "========================================"
echo "  Discord Event Tracker Bot Startup"
echo "========================================"
echo

source "${BASH_SOURCE[0]%/*}/init.sh"

# Set default ENV_FILE if not set
if [ -z "$ENV_FILE" ]; then
    ENV_FILE=".env"
fi

# Check if environment file exists
if [ ! -f "$ENV_FILE" ]; then
    echo
    echo "WARNING: $ENV_FILE not found!"
    if [ "$ENV_FILE" == ".env" ]; then
        echo "Please copy env_example.txt to .env and add your Discord bot token"
        echo
        echo "Creating .env file from template..."
        cp env_example.txt .env
        echo
        echo "Please edit .env file and add your Discord bot token, then run this script again."
    else
        echo "Please ensure $ENV_FILE exists with your configuration."
    fi
    read -p "Press Enter to exit..."
    exit 1
fi

# Check if Discord token is set
echo
echo "Checking Discord bot token in $ENV_FILE..."
if grep -q "DISCORD_TOKEN=your_bot_token_here" "$ENV_FILE"; then
    echo "ERROR: Discord bot token not configured!"
    echo "Please edit $ENV_FILE file and replace 'your_bot_token_here' with your actual bot token"
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

export PYTHONIOENCODING=utf-8
export PYTHONPATH="${BASH_SOURCE[0]%/*}/src"
python -m distro_event_tracker

# If we get here, the bot stopped
echo
echo "Bot has stopped."
read -p "Press Enter to exit..."
