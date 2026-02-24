# Discord Event Tracker Bot

A robust Discord bot for tracking gaming events and attendance through custom emoji reactions. Designed for high-volume guilds, it features weighted scoring, deterministic ID-based tracking, and smart participation reminders.

## 🚀 Key Features

- **Consolidated Smart Summary**: A single `!summary` command that intelligently handles Event IDs, ranges, "Last N" events, and date-based fallbacks.
- **Participation Reminders**: Automatically DMs active players who forget to react to a new event within 2 minutes (if the event started within 2 hours of the previous one).
- **Discord-Native Timestamps**: Uses Discord's server time (`created_at`) as the source of truth to eliminate "desync" between the bot and users.
- **Multi-Instance Support**: Easily run multiple bot instances (e.g., "Distro" and "Ocean") from a single codebase using dedicated environment files.
- **Deterministic Tracking**: Move beyond brittle "start/end seconds" math. Use specific Event IDs for 100% accurate, inclusive range reports.
- **Auto-Recovery**: Rebuilds the entire event state from Discord message history on startup (No database required).
- **Advanced Logging**: Persistent file-based logs with configurable paths for every instance.

---

## 🛠️ Deployment & Setup

### 1. Prerequisites
- **Python 3.10+**
- **Git**
- A Discord Bot Token (via the [Discord Developer Portal](https://discord.com/developers/applications))

### 2. Installation
Clone the repository and enter the directory:
```bash
git clone https://github.com/psteijn/distro_event_tracker.git
cd distro_event_tracker
```

### 3. Configuration
The bot uses `.env` files for configuration. 
1. Copy `env_example.txt` to `.env`.
2. Fill in your `DISCORD_TOKEN` and `EVENT_CHANNEL_ID`.

**Customizing Multipliers & Emojis:**
Edit `config.py` to change scoring weights or custom emoji names (e.g., `share_100`, `share_75`).

### 4. Running the Bot
The bot includes convenience scripts for different environments:

#### **Standard Startup (using .env):**
- **Windows:** `start_bot.bat`
- **Linux/Shell:** `./start_bot.sh`

#### **Multi-Instance Startup:**
If you want to run two different bots (e.g., for different guilds or purposes):
1. Create `.env.distro` and `.env.ocean`.
2. Run `start_distro.bat` or `start_ocean.bat`.
*These scripts automatically load their respective environment files and log to separate files.*

---

## 🎮 Command Guide

### Event Creation
| Command | Multiplier | Icon | Description |
| :--- | :--- | :--- | :--- |
| `!dungeon <name>` | 1.0x | 🏰 | Standard dungeon run. |
| `!miniboss <name>` | 1.0x | ⚔️ | Miniboss encounter. |
| `!t8 <name>` | 1.0x | 🗺️ | Tier 8 map group. |
| `!boss <name>` | 2.0x | 👹 | Main boss event (Double Points). |
| `!omniboss <name>` | 8.0x | 👑 | Massive guild event (8x Points). |

### The Unified `!summary` Command
The new summary command is context-aware and accepts multiple formats:

- **`!summary last 5`**: Summarizes the 5 most recent events.
- **`!summary <id1> <id2>`**: Summarizes everything between two Event IDs (inclusive).
- **`!summary <event_id>`**: Provides a detailed summary for a single specific event.
- **`!summary 2024-01-15`**: (Fallback) Summarizes events starting from a specific date.

### Administrative Tools
- **`!add_users <id> <multiplier> @user...`**: Manually add attendees with a specific weight (1.0, 0.75, 0.5, 0.25).
- **`!rename <id> <new_name>`**: Updates the event name in memory and on the original Discord message.
- **`!delete_event <id>`**: Removes the event and its Discord message (Creator only).
- **`!missing`**: Compares the last two events and lists users who missed the most recent one.

---

## 🧠 Smart Reminders Logic
To maintain momentum during "Distros," the bot helps remind active players to react:
1. When Event B starts, the bot checks if Event A happened within the last **2 hours**.
2. If yes, it waits **120 seconds**.
3. It then re-fetches the reactions for **both events**.
4. Anyone who reacted to Event A but is "missing" from Event B gets a polite DM with a **jump-link** to the new event.

---

## 🧪 Development & Testing
To run the automated test suite (42+ tests covering range logic, scoring, and reminders):
- **Windows:** `run_tests.bat`
- **Linux/Shell:** `./run_tests.sh`

---

## 🔒 Security Note
- Never commit your `.env` files.
- The project includes a `.gitignore` that automatically excludes `.env*` and all `*.log` files to protect your tokens and local data.
