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

### 2. Local Windows development
Clone the repository and enter the directory:
```bash
git clone https://github.com/psteijn/distro_event_tracker.git
cd distro_event_tracker
```

Create the isolated development environment and run all checks:

```powershell
.\bootstrap-dev.ps1
.\check.bat
```

The check suite does not require Discord credentials or an `.env` file.

### 3. Configuration
The bot uses `.env` files for configuration.
1. Copy `.env.distro.example` to `.env` for a single local instance, or copy the two example files to ignored `.env.distro` and `.env.ocean` files for production-shaped local instances.
2. Fill in your `DISCORD_TOKEN` and `EVENT_CHANNEL_ID`.

**Customizing Multipliers & Emojis:**
Edit `src/distro_event_tracker/config.py` to change scoring weights or custom emoji names
(e.g., `share_100`, `share_75`).

### 4. Running the Bot
The bot includes convenience scripts for different environments:

#### **Standard Startup (using .env):**
- **Windows:** `start_bot.bat`
- **Linux/Shell:** `./start_bot.sh`

#### **Multi-Instance Startup:**
If you want to run two different bots (e.g., for different guilds or purposes):
1. Create `.env.distro` and `.env.ocean`.
2. Give each instance its own event channel and slash command name:
   - `.env.distro`: `EVENT_CHANNEL_ID=<distro-channel-id>` and `EVENT_COMMAND_NAME=event`
   - `.env.ocean`: `EVENT_CHANNEL_ID=<ocean-channel-id>` and `EVENT_COMMAND_NAME=ocean`
3. Run `start_distro.bat` or `start_ocean.bat`.
*These scripts automatically load their respective environment files and log to separate files.*

#### **Ubuntu Podman deployment from Windows:**

Production source is packaged from the clean Windows Git checkout and sent to the SSH alias
`steijnserver`. Ubuntu does not contain a Git checkout or the originating env files.

```powershell
.\deploy.ps1 -DryRun             # preview the Podman Quadlet diff
.\deploy.ps1                     # deploy clean HEAD == origin/main
.\deploy.ps1 -SyncSecrets        # explicitly synchronize env files and deploy
.\deploy.ps1 -SecretsOnly        # rotate configuration and restart both bots
.\deploy.ps1 -VerifyFullInitialization # opt into waiting for history reconstruction
.\deploy.ps1 -Rollback <full-sha>
.\ops\remote-status.ps1 -Since 1h
```

Normal deployments preserve the existing remote environment files. Secret-changing commands read
the ignored `.env.distro` and `.env.ocean` files locally and stream them atomically over SSH to
mode-`0600` files in the `psteijn` user's Podman configuration directory. The one-time migration
from MicroK8s was completed in July 2026; production now runs only the two rootless Podman
Quadlets. Health becomes ready when the Discord gateway connects, while deployment verification
uses a bounded two-minute startup gate: the intended image must be healthy, connect to Discord,
reconstruct three events, and emit no error-level startup signals. A failed release deploy rolls
both bots back to the prior retained release. Use `-VerifyFullInitialization` only when the final
historical reconstruction marker is required.

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

You can also create any event with the configured event slash command, such as
`/event type:<type> name:<name>` or `/ocean type:<type> name:<name>`. Discord requires
both options before the command can be submitted, and each command only works in its
bot instance's configured event channel.

### Event planning

Set `PLANNING_CHANNEL_ID` to enable `/plan` in one channel. `/plan create` asks the
organizer privately to choose a timezone, one of today through the next fourteen days,
and a half-hour availability window of up to ten hours. Members react to each block
they can attend; the card shows every time in each viewer's Discord-local timezone and
a copyable plan ID. The leader uses `/plan schedule start:<slot> end:<slot>` to choose
an inclusive range of the numbered slots and notify members who reacted to an
overlapping block. `/plan schedule` and `/plan cancel` use the leader's most recent
open plan by default; either accepts `id:<plan ID>` to target a specific poll.

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

For the complete non-mutating validation suite, including formatting, lint, typing,
architecture contracts, tests, and coverage, run `check.bat` or `./check.sh`. The scripts
create `.venv` when needed and never require production configuration.

---

## 🔒 Security Note
- Never commit your `.env` files.
- The project includes a `.gitignore` that automatically excludes `.env*` and all `*.log` files to protect your tokens and local data.

## Passwordless operations

See the [server access contract](docs/server-access.md) for explicit accounts, non-interactive
SSH, recovery, and deployment verification. Never repoint the shared alias to codex.
