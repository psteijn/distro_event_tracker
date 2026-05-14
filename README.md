# Discord Event Tracker Bot

A robust Discord bot for tracking gaming events and attendance through custom emoji reactions. Designed for high-volume guilds, it features weighted scoring, deterministic ID-based tracking, and smart participation reminders.

## 🚀 Key Features

- **Intelligent Event Summaries**: Get detailed attendance reports for a single run, a specific range of runs, or just your most recent activity using one simple command.
- **Automatic Participation Reminders**: Helps keep your group together by sending a polite DM to players who attended the last run but haven't signed up for the new one yet.
- **Weighted Scoring System**: Different event types (like Bosses vs. Dungeons) give different point values, ensuring players are fairly rewarded for more difficult content.
- **Instant Setup & Recovery**: The bot builds its memory directly from your channel history. No database is required, and the bot "remembers" everything instantly after a restart.
- **Accurate Time Tracking**: Uses Discord's server time as the source of truth, so your summaries and timestamps are always perfectly synced with the chat.
- **Multi-Group Support**: Easily run separate bot instances for different teams or guilds from a single installation.

---

## 🛠️ Deployment & Setup

### 1. Prerequisites
- **Python 3.10+**
- **Git**
- **A Discord Bot Token**: Follow the steps below to create one.

#### 🔑 How to get a Discord Bot Token
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **"New Application"** and give it a name (e.g., "Event Tracker").
3. On the left sidebar, click **"Bot"**.
4. Click **"Reset Token"** (or "Copy") to get your unique token. **Keep this secret!**
5. Scroll down to the **"Privileged Gateway Intents"** section. This is critical:
   - Enable **"Message Content Intent"** (so the bot can read `!commands`).
   - Enable **"Server Members Intent"** (so the bot can find users for DMs).
   - Click **"Save Changes"**.
6. On the left sidebar, go to **"OAuth2"** -> **"URL Generator"**.
7. Under **Scopes**, select `bot`.
8. Under **Bot Permissions**, select:
   - `Read Messages/View Channels`
   - `Send Messages`
   - `Manage Messages` (optional, for deleting events)
   - `Embed Links`
   - `Read Message History` (required for recovery)
   - `Add Reactions`
9. Copy the generated URL at the bottom and paste it into your browser to invite the bot to your server.

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

#### **Automated Deployment (Windows Task Scheduler):**
If the bot is running as a Windows Scheduled Task, you can use the deployment scripts to automatically restart the tasks with the latest code:
- Run `deploy.bat` (requires PowerShell permissions to stop/start tasks).
*This script restarts both `DistroEventTracker` and `OceanDistroEventTracker` tasks.*

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

### The Raw Data Command: `!data`

The `!data` command is designed for data extraction, providing raw attendance info with participation weights. It supports the same flexible arguments as `!summary`.

- **`!data last 5`**: Raw data for the 5 most recent events.
- **`!data <id1> <id2>`**: Raw data for events between two IDs.

**Output Format:**
`[event_id] Event Name (multiplier): User1 (score), User2 (score), ...`

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
