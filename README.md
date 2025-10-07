# Discord Event Tracker Bot

A Discord bot for tracking gaming events and attendance through custom emoji reactions. Users can create different types of events (dungeons, minibosses, bosses) with weighted scoring, register attendance by reacting with custom emojis, and generate comprehensive attendance summaries with weighted averages.

## Features

- **Three Event Types**: Create dungeon (1x), miniboss (1x), and boss (2x) events with different multipliers
- **Custom Emoji Reactions**: Users register attendance levels using custom emoji reactions (100%, 75%, 50%, 25%)
- **Weighted Scoring System**: Events have multipliers that affect final attendance scores
- **Manual Attendance**: Add users manually to events with the `add_users` command
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
   EVENT_CHANNEL_ID=your_channel_id_here
   ```
   
   **Note:** The bot prefix and emoji names are configured in `config.py` and can be customized there.

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

### Event Creation Commands

#### `!dungeon Dungeon Name`
Creates a new dungeon event with 1x multiplier.

**Example:**
```
!dungeon Ancient Ruins
!dungeon Crystal Caverns
```

#### `!miniboss Miniboss Name`
Creates a new miniboss event with 1x multiplier.

**Example:**
```
!miniboss Shadow Dragon
!miniboss Ice Golem
```

#### `!boss Boss Name`
Creates a new boss event with 2x multiplier (double points).

**Example:**
```
!boss Demon Lord
!boss Final Boss
```

### `!add_users EVENT_ID @user1 @user2 @user3`
Manually add users to an existing event. Users added this way get full attendance (100%) with a 🐈 emoji.

**Example:**
```
!add_users 1234567890_1234567890 @alice @bob @charlie
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

1. **Create Events**: Use `!dungeon`, `!miniboss`, or `!boss` commands to create different types of events
2. **Register Attendance**: React to event messages with custom emojis to register your attendance level
3. **Add Users Manually**: Use `!add_users` to manually add users to events
4. **Generate Summaries**: Use `!summary` with timestamps to get attendance reports with weighted scoring

## Attendance System

### Custom Emoji Reactions
The bot uses custom emoji reactions for attendance tracking:

- **`share_100`** - 100% attendance (1.0x participation multiplier)
- **`share_75`** - 75% attendance (0.75x participation multiplier)  
- **`share_50`** - 50% attendance (0.5x participation multiplier)
- **`share_25`** - 25% attendance (0.25x participation multiplier)

### Event Multipliers
Different event types have different multipliers that affect final scoring:

- **Dungeon Events** (`!dungeon`) - 1x multiplier
- **Miniboss Events** (`!miniboss`) - 1x multiplier  
- **Boss Events** (`!boss`) - 2x multiplier (double points)

### Scoring Formula
**Final Score = Event Multiplier × Participation Multiplier**

- A user who attends a boss event with 100% participation gets: 2.0 × 1.0 = 2.0 points
- A user who attends a dungeon event with 75% participation gets: 1.0 × 0.75 = 0.75 points
- Manual attendance (via `!add_users`) always gets 1.0x participation multiplier

## Output Format

The summary command outputs clean, readable text with weighted averages:

```
📊 Event Attendance Summary
Events from 2024-01-01 to 2024-01-31 (Pacific Time)
Total Events: 5

🏰 Ancient Ruins: John, Jane, Bob
⚔️ Shadow Dragon: Alice, Charlie, John
👹 Demon Lord: Bob, Jane
🏰 Crystal Caverns: Alice, John, Charlie
⚔️ Ice Golem: Jane, Bob, Alice

-------
Events: Ancient Ruins, Shadow Dragon, Demon Lord, Crystal Caverns, Ice Golem
ALL EVENTS: John (3.0), Jane (3.0), Bob (3.0), Alice (2.0), Charlie (1.0)
```

**Key Features:**
- **Event List**: Shows each event with attendees (includes event type emojis)
- **Event Names**: Lists all event names in the summary
- **Weighted Summary**: "ALL EVENTS" line shows most active attendees with weighted scores
- **Pacific Timezone**: All timestamps displayed in Pacific timezone
- **Clean Format**: Easy to read and parse
- **Scoring**: Scores reflect both event multipliers and participation levels

## Configuration

Edit `config.py` to customize:
- Bot command prefix (default: `!`)
- Designated event channel (optional)
- Custom emoji names for attendance reactions:
  - `EMOJI_HUNDRED` (default: `share_100`)
  - `EMOJI_SEVENTY_FIVE` (default: `share_75`)
  - `EMOJI_FIFTY` (default: `share_50`)
  - `EMOJI_TWENTY_FIVE` (default: `share_25`)
- Database path (for future SQLite implementation)

## Technical Details

- **User Tracking**: Internally tracks account names for accurate identification
- **Display Names**: Shows user display names in summaries for better readability
- **In-Memory Storage**: Events are stored in memory with automatic recovery from message history
- **Event Reconstruction**: Automatically rebuilds events from Discord message history on startup
- **Custom Emoji Support**: Uses custom Discord emojis for attendance tracking
- **Weighted Scoring System**: Calculates scores using event multipliers and participation levels
- **Manual Attendance**: Supports adding users manually with full attendance credit
- **Flexible Parsing**: Supports multiple timestamp formats with intelligent parsing
- **Message Splitting**: Automatically handles long outputs by splitting into multiple messages
- **Timezone Handling**: All timestamps in Pacific timezone with automatic daylight savings
- **Quote Support**: Handles quoted timestamps for complex date/time strings
- **Parallel Processing**: Fast startup with optimized channel scanning
- **Permission Handling**: Gracefully handles channels without read permissions
- **Reaction Processing**: Efficiently processes emoji reactions for attendance tracking
- **Error Recovery**: Continues operation even if some channels fail to load
- **Event Types**: Supports three distinct event types with different scoring multipliers

## Startup Process

When the bot starts up, it automatically:

1. **Connects to Discord** and shows guild count
2. **Scans message history** from the designated event channel
3. **Reconstructs events** and attendance data from embeds and reactions
4. **Processes custom emojis** and attendance levels
5. **Reports results** showing how many events were reconstructed
6. **Ready for use** with full historical data restored

**Console Output Example:**
```
🔄 Reconstructing events from message history...
📖 Scanning channel: events in My Server
📝 Reconstructed event: Ancient Ruins (ID: 1234567890_1704067200, multiplier: 1.0x, attendance: ['John', 'Jane'])
📝 Reconstructed event: Demon Lord (ID: 1234567891_1704153600, multiplier: 2.0x, attendance: ['Bob', 'Alice'])
✅ Reconstructed 2 events from message history
🚀 Bot ready! Reconstructed 2 events from history.
```
