# Gemini Project Instructions: Distro Event Tracker

These instructions are foundational mandates for all Gemini sessions working in this repository. They take absolute precedence over general workflows.

## 🏛️ Architectural Mandates (CRITICAL)
### 1. Database-less Persistence
- **Rule:** The bot MUST remain stateless. It reconstructs memory by scanning channel history.
- **Constraint:** Any data that needs to survive a restart (attendance, event names, multipliers) MUST be stored within the Discord message itself (Embed Title, Fields, or Footer).
- **Warning:** Changing the Embed Title prefix (e.g., "🏰 ") or Footer format ("Event ID: {id}") will break the `reconstruct_from_history` logic.

### 2. Scoring Logic
- **Formula:** `Final Score = Event Multiplier (1x/2x/8x) * Participation Multiplier (1.0/0.75/0.5/0.25)`.
- **Validation:** Always verify both multipliers when modifying summary or data export logic.

### 3. Message Chunking
- **Mandate:** Never use simple character-count splitting for long Discord messages.
- **Pattern:** Use the `send_long_message(ctx, blocks)` helper.
- **Rule:** Pass data as a `List[str]` where each string is an unbreakable block (e.g., one entire event record) to prevent "spurious linebreaks" in the middle of records.

### 4. Manual Attendance & Transparency
- **Mandate:** All manual attendance entries (via `!add_users` or `!backfill`) must be visible in the event embed for audit purposes.
- **Pattern:** Use the `update_embed_manual_attendance(embed, manual_attendance)` helper function to ensure consistent formatting and emoji display.

### 5. Raw Data Format (`!data`)
- **Format:** `[event_id] [event_type] name: user1 (score), user2 (score)`
- **Rule:** Maintain the bracketed type and specific colon/comma spacing for parsability by external tools.

### 6. Natural Language Help (`!ask`)
- **Mandate:** The `!ask` command MUST use `gemini-cli` in a strict read-only sandbox.
- **Pattern:** Use `gemini.cmd --prompt "..." --approval-mode=plan --skip-trust`.
- **Constraint:** Never allow the `!ask` command to run without the `plan` approval mode, as it prevents any modifications to the codebase or environment.

## 🛠️ Tech Stack & Standards
- **Language:** Python 3.10+ (f-strings and type hinting required)
- **Bot Framework:** `discord.py`
- **Formatting:** Black (run `./lint.sh` or `lint.bat` before every commit)
- **Linting:** Ruff
- **Testing:** `pytest` (with `pytest-asyncio`)
- **Timezone:** Always use `PACIFIC_TZ` (US/Pacific) for event creation and display.

## 🧪 Testing & CI Workflow
- **Pre-commit:** You MUST run `run_tests.sh` and `lint.sh`.
- **Mocking:** Use the `tests/utils_discord_mocks.py` framework. Never attempt to connect to the real Discord API during unit tests.
- **GitHub:** This repo uses standard feature branching. Do not commit to `main` directly; propose a branch and PR.

## 🔄 Standard Workflow After Changes
After implementing any feature or fix, follow these steps to ensure quality and successful deployment:

1. **Validate Quality:**
   - Run `.\lint.bat` (or `./lint.sh`) to ensure code style compliance.
   - Run `.\run_tests.bat` (or `./run_tests.sh`) to verify all unit tests pass.

2. **Deploy & Verify:**
   - Run `.\deploy.bat` to restart the Windows Task Scheduler tasks (`DistroEventTracker` and `OceanDistroEventTracker`).
   - **Check Status (Gemini-Friendly):** Run `python deploy_report.py`. This script provides a high-signal summary of the logs (bot name, emoji status, and last event) to avoid reading raw log files.

3. **Source Control:**
   - Once verified, commit the changes with a descriptive message.
   - Push the changes to the `main` branch (or your feature branch as appropriate) in the GitHub repository.

## 🏷️ Event Mappings
Maintain the following emoji-to-type mapping in `EVENT_TYPE_MAP` and `BACKFILL_TYPE_MAP`:
- 🏰 -> `dungeon` (1x)
- ⚔️ -> `mini` (1x)
- 🗺️ -> `t8` (1x)
- 👹 -> `main` / `boss` (2x)
- 👑 -> `omni` (8x)
