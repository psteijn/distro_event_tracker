# Discord Event Tracker Bot

A Discord bot for tracking events and attendance through emoji reactions.

## Features

- Create events by messaging the bot
- Users can react with emojis to register attendance
- Generate attendance summaries for specific time ranges
- Export attendance data in a structured format

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file with your Discord bot token:
   ```
   DISCORD_TOKEN=your_bot_token_here
   ```

3. Run the bot:
   
   **Windows (Command Prompt/PowerShell):**
   ```cmd
   start_bot.bat
   ```
   
   **Windows (Git Bash/WSL):**
   ```bash
   ./start_bot.sh
   ```
   
   **Manual start:**
   ```bash
   python main.py
   ```

## Usage

- Message the bot to create events: `!create_event Event Name`
- React to event messages with emojis to register attendance
- Request summaries: `!summary YYYY-MM-DD YYYY-MM-DD`

## Configuration

Edit `config.py` to customize bot behavior, channels, and settings.
