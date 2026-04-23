# Gemini Project Instructions: Distro Event Tracker

These instructions are foundational mandates for all Gemini sessions working in this repository. They take absolute precedence over general workflows.

## 🛠️ Tech Stack & Standards
- **Language:** Python 3.7+
- **Bot Framework:** `discord.py`
- **Formatting:** Black (configured in `pyproject.toml`)
- **Linting:** Ruff
- **Testing:** `pytest` (with `pytest-asyncio`)

## 📋 Commands & Workflows
- **Linting:** Always run `./lint.sh` (Linux) or `lint.bat` (Windows) before committing. This runs Black and Ruff fix.
- **Testing:** Always run `./run_tests.sh` (Linux) or `run_tests.bat` (Windows) to verify changes.
- **Timezone:** Always use `PACIFIC_TZ` (US/Pacific) for event creation and display.

## 🏛️ Architectural Patterns
### 1. Message Chunking
- **Mandate:** Never use simple character-count splitting for long Discord messages.
- **Pattern:** Use the `send_long_message(ctx, blocks)` helper.
- **Rule:** Pass data as a `List[str]` where each string is an unbreakable block (e.g., one entire event record) to prevent "spurious linebreaks" in the middle of records.

### 2. Manual Attendance & Transparency
- **Mandate:** All manual attendance entries (via `!add_users` or `!backfill`) must be visible in the event embed for audit purposes.
- **Pattern:** Use the `update_embed_manual_attendance(embed, manual_attendance)` helper function to ensure consistent formatting and emoji display.

### 3. Raw Data Format (`!data`)
- **Format:** `[event_id] [event_type] name: user1 (score), user2 (score)`
- **Rule:** Maintain the bracketed type and specific colon/comma spacing for parsability by external tools.

## 🏷️ Event Mappings
Maintain the following emoji-to-type mapping in `EVENT_TYPE_MAP` and `BACKFILL_TYPE_MAP`:
- 🏰 -> `dungeon` (1x)
- ⚔️ -> `mini` (1x)
- 🗺️ -> `t8` (1x)
- 👹 -> `main` / `boss` (2x)
- 👑 -> `omni` (8x)
