# Discord Event Tracker Bot

A Discord bot for tracking events and attendance through emoji reactions. Users can create events, register attendance by reacting with emojis, and generate comprehensive attendance summaries with weighted averages.

## Features

- **Event Creation**: Create events with custom names using simple commands
- **Emoji Reactions**: Users register attendance by reacting to event messages
- **Flexible Timestamps**: Support for multiple timestamp formats including full timestamps and epoch seconds
- **Smart Summaries**: Generate attendance summaries with optional end timestamps
- **Weighted Averages**: Shows most active attendees across all events with attendance scores
- **Display Names**: Shows user display names in summaries for better readability
- **Simple Text Output**: Clean, readable text format instead of complex JSON
- **Account Name Tracking**: Internally tracks account names for accurate user identification
- **Automatic Recovery**: Rebuilds events from message history on restart (no database required)
- **Pacific Timezone**: All timestamps handled in Pacific timezone with automatic daylight savings
- **Quoted Timestamps**: Supports quoted timestamps for complex date/time strings
- **Parallel Processing**: Fast startup with optimized channel scanning

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
!summary 2024-01-01                           # All events after Jan 1
!summary "2024-01-01"                         # Same as above (quoted)
!summary 2024-01-01 2024-01-31               # Events in January
!summary "2024-01-01" "2024-01-31"           # Same as above (quoted)
!summary 2024-01-15 14:30:00                 # All events after 2:30 PM on Jan 15
!summary "2024-01-15 14:30:00"               # Same as above (quoted)
!summary 2024-01-01 09:00:00 2024-01-01 18:00:00  # Events on Jan 1, 9am-6pm
!summary "2024-01-01 09:00:00" "2024-01-01 18:00:00"  # Same as above (quoted)
!summary 1704067200                          # All events after epoch timestamp
```

### `!help_events`
Shows detailed help information about all available commands and timestamp formats.

## Usage

1. **Create Events**: Use `!create_event Event Name` to create a new event
2. **Register Attendance**: React to event messages with emojis to register your attendance
3. **Generate Summaries**: Use `!summary` with timestamps to get attendance reports

## Output Format

The summary command outputs clean, readable text with weighted averages:

```
📊 Event Attendance Summary
Events from 2024-01-01 to 2024-01-31 (Pacific Time)
Total Events: 5

Gaming Night: John, Jane, Bob
Movie Night: Alice, Charlie, John
Team Meeting: Bob, Jane
Study Group: Alice, John, Charlie
Social Event: Jane, Bob, Alice

ALL EVENTS: John (4), Jane (4), Bob (4), Alice (3), Charlie (2)
```

**Key Features:**
- **Event List**: Shows each event with attendees
- **Weighted Summary**: "ALL EVENTS" line shows most active attendees with attendance scores
- **Pacific Timezone**: All timestamps displayed in Pacific timezone
- **Clean Format**: Easy to read and parse

## Configuration

Edit `config.py` to customize:
- Bot command prefix
- Designated event channel (optional)
- Default emoji for reactions
- Other bot settings

## Technical Details

- **User Tracking**: Internally tracks account names for accurate identification
- **Display Names**: Shows user display names in summaries for better readability
- **In-Memory Storage**: Events are stored in memory with automatic recovery from message history
- **Flexible Parsing**: Supports multiple timestamp formats with intelligent parsing
- **Message Splitting**: Automatically handles long outputs by splitting into multiple messages
- **Timezone Handling**: All timestamps in Pacific timezone with automatic daylight savings
- **Quote Support**: Handles quoted timestamps for complex date/time strings
- **Parallel Processing**: Fast startup with optimized channel scanning
- **Permission Handling**: Gracefully handles channels without read permissions
- **Reaction Processing**: Efficiently processes emoji reactions for attendance tracking
- **Weighted Scoring**: Calculates attendance scores across all events in time range
- **Error Recovery**: Continues operation even if some channels fail to load

## Startup Process

When the bot starts up, it automatically:

1. **Connects to Discord** and shows guild count
2. **Scans message history** from all accessible channels (or designated channel)
3. **Reconstructs events** and attendance data from embeds and reactions
4. **Reports results** showing how many events were reconstructed
5. **Ready for use** with full historical data restored

**Console Output Example:**
```
🔄 Reconstructing events from message history...
📖 Scanning channel: events in My Server
📝 Reconstructed event: Gaming Night (ID: 1234567890_1704067200)
📝 Reconstructed event: Movie Night (ID: 1234567891_1704153600)
✅ Reconstructed 2 events from message history
🚀 Bot ready! Reconstructed 2 events from history.
```
