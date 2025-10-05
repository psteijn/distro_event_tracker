# Discord Event Tracker Bot

A Discord bot for tracking events and attendance through emoji reactions. Users can create events, register attendance by reacting with emojis, and generate comprehensive attendance summaries.

## Features

- **Event Creation**: Create events with custom names using simple commands
- **Emoji Reactions**: Users register attendance by reacting to event messages
- **Flexible Timestamps**: Support for multiple timestamp formats including full timestamps and epoch seconds
- **Smart Summaries**: Generate attendance summaries with optional end timestamps
- **Display Names**: Shows user display names in summaries for better readability
- **Simple Text Output**: Clean, readable text format instead of complex JSON
- **Account Name Tracking**: Internally tracks account names for accurate user identification

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create a `.env` file with your Discord bot token:**
   ```
   DISCORD_TOKEN=your_bot_token_here
   BOT_PREFIX=!
   EVENT_CHANNEL_ID=your_channel_id_here
   DEFAULT_EMOJI=✅
   ```

3. **Run the bot:**
   
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

## Commands

### `!create_event Event Name`
Creates a new event that users can react to for attendance tracking.

**Example:**
```
!create_event Gaming Night
!create_event Team Meeting
```

### `!summary START_TIMESTAMP [END_TIMESTAMP]`
Generates attendance summary for events in a time range. The end timestamp is optional - if omitted, shows all events after the start timestamp.

**Supported timestamp formats:**
- `YYYY-MM-DD` (date only)
- `YYYY-MM-DD HH:MM:SS` (full timestamp)
- `YYYY-MM-DD HH:MM` (date with time)
- `YYYY/MM/DD` (alternative format)
- `MM/DD/YYYY` (US format)
- `1234567890` (epoch seconds)

**Examples:**
```
!summary 2024-01-01                    # All events after Jan 1
!summary 2024-01-01 2024-01-31        # Events in January
!summary 2024-01-15 14:30:00          # All events after 2:30 PM on Jan 15
!summary 2024-01-01 09:00:00 2024-01-01 18:00:00  # Events on Jan 1, 9am-6pm
!summary 1704067200                   # All events after epoch timestamp
```

### `!help_events`
Shows detailed help information about all available commands and timestamp formats.

## Usage

1. **Create Events**: Use `!create_event Event Name` to create a new event
2. **Register Attendance**: React to event messages with emojis to register your attendance
3. **Generate Summaries**: Use `!summary` with timestamps to get attendance reports

## Output Format

The summary command outputs clean, readable text:

```
📊 Event Attendance Summary
Events from 2024-01-01 to 2024-01-31
Total Events: 3

Gaming Night: John, Jane, Bob
Movie Night: Alice, Charlie
Team Meeting: (no attendees)
```

## Configuration

Edit `config.py` to customize:
- Bot command prefix
- Designated event channel (optional)
- Default emoji for reactions
- Other bot settings

## Technical Details

- **User Tracking**: Internally tracks account names for accurate identification
- **Display Names**: Shows user display names in summaries for better readability
- **In-Memory Storage**: Events are stored in memory (database integration planned)
- **Flexible Parsing**: Supports multiple timestamp formats with intelligent parsing
- **Message Splitting**: Automatically handles long outputs by splitting into multiple messages
