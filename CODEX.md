# Codex Project Instructions: Distro Event Tracker

These instructions are the operational guide for Codex sessions working in this repository. Follow them alongside the repository code and tests.

## Core Rules

### 1. Database-less persistence
- The bot must remain stateless.
- Any data that must survive a restart, such as attendance, event names, multipliers, and dibs state, must be recoverable from Discord message history.
- Do not change embed title prefixes or footer formats without checking the reconstruction logic first.

### 2. Scoring logic
- Final score = event multiplier x participation multiplier.
- Event multipliers currently include 1x, 2x, and 8x.
- Participation multipliers currently include 1.0, 0.75, 0.5, and 0.25.

### 3. Long message handling
- Do not hand-roll naive string splitting for long Discord messages.
- Use `send_long_message(ctx, blocks)` and pass a list of full blocks when possible.
- Keep records intact so long outputs do not get broken in the middle of a logical entry.

### 4. Manual attendance
- Manual attendance entries must stay visible in the embed for auditability.
- Use `update_embed_manual_attendance(embed, manual_attendance)` when formatting or refreshing those fields.

### 5. Raw data format
- Preserve the `!data` output shape: `[event_id] [event_type] name: user1 (score), user2 (score)`.
- Keep the bracketed type and punctuation consistent so downstream tools can parse it.

## Working Standards

- Language: Python 3.10+.
- Framework: `discord.py`.
- Formatting: Black.
- Linting: Ruff.
- Testing: `pytest` with `pytest-asyncio`.
- Timezone: Use `PACIFIC_TZ` for event creation and display.

## Standard Workflow

When you finish a code change, use this sequence:

1. Format and lint:
   - Run `.\lint.bat` on Windows.
   - Run `./lint.sh` on shell-based environments.
2. Run tests:
   - Run `.\run_tests.bat` on Windows.
   - Run `./run_tests.sh` on shell-based environments.
3. Deploy:
   - Run `.\deploy.bat` to restart the scheduled tasks.
4. Verify logs:
   - Run `python deploy_report.py` right after deploy.
   - Check `distro_task_log.txt` and `ocean_distro_task_log.txt` for fresh errors.
   - Confirm the latest log lines show the bots connecting cleanly and not emitting new errors.
   - If anything looks off, keep watching the logs until the startup path is clearly healthy or the failure is understood.

## Event Mappings

Keep these mappings aligned in `EVENT_TYPE_MAP` and `BACKFILL_TYPE_MAP`:

- Dungeon emoji -> `dungeon` (1x)
- Miniboss emoji -> `mini` / `miniboss` (1x)
- T8 emoji -> `t8` (1x)
- Boss emoji -> `main` / `boss` (2x)
- Omniboss emoji -> `omni` / `omniboss` (8x)
