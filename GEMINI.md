# Gemini Project Instructions: Distro Event Tracker

These repository-specific instructions supplement `AGENTS.md`. Follow `AGENTS.md`
for the authoritative development, deployment, secret-handling, and runtime rules.

## Architectural mandates

### Database-less event persistence

- The bot reconstructs event state by scanning Discord channel history.
- Persistent attendance, event names, and multipliers must remain encoded in the
  Discord message embed.
- Changing the embed title prefix or the `Event ID: {id}` footer format requires
  updating and testing history reconstruction.

### Scoring

`Final Score = Event Multiplier (1x/2x/8x) * Participation Multiplier (1.0/0.75/0.5/0.25)`

Verify both multipliers when changing summary or export behavior.

### Long Discord messages

- Do not split long messages using only character counts.
- Use `send_long_message(ctx, blocks)` with one unbreakable record per block.

### Manual attendance

Manual attendance added with `!add_users` or `!backfill` must remain visible in
the event embed. Use `update_embed_manual_attendance` for consistent formatting.

### Raw-data compatibility

Preserve the `!data` record format:

`[event_id] [event_type] name: user1 (score), user2 (score)`

## Development and validation

- Use Python 3.10 or newer and the project `.venv`.
- Use `discord.py`, Black, Ruff, mypy, pytest, and import-linter as configured.
- Use `PACIFIC_TZ` for event creation and display.
- Never connect unit tests to the real Discord API.
- Prefer the mocks in `tests/utils_discord_mocks.py`.
- Run `.\check.bat` on Windows or `./check.sh` on Linux before publishing.
- Validation must work without production environment files.

## Deployment and operations

- Windows is the Git checkout and plaintext-secret authority.
- Production runs on the approved Ubuntu target `steijnserver` under MicroK8s.
- Run `.\deploy.bat -DryRun` before production deployment when practical.
- Run `.\deploy.bat` for a code-only immutable deployment; it preserves
  Kubernetes Secrets.
- Use `.\deploy.bat -SyncSecrets` or `.\deploy.bat -SecretsOnly` only when
  secret synchronization is explicitly requested.
- Inspect production with:

  `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\ops\remote-status.ps1 -Since 10m`

- Roll back with `.\deploy.bat -Rollback <full-sha>`.
- Do not create a Git checkout, Git credentials, or plaintext env files on Ubuntu.

## Event mappings

Keep `EVENT_TYPE_MAP` and `BACKFILL_TYPE_MAP` aligned:

- 🏰 → `dungeon` (1x)
- ⚔️ → `mini` (1x)
- 🗺️ → `t8` (1x)
- 👹 → `main` / `boss` (2x)
- 👑 → `omni` (8x)
