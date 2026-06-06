# Persistence Contracts

Discord message history is the production datastore. These formats are public,
backward-compatible contracts.

- Event embeds use recognized emoji title prefixes.
- Event footers use `Event ID: <id>`.
- Event embeds use `Created by` and `Manual Attendance` field names.
- Dibs state supports the current `https://dibs.data?payload=` format and all legacy
  formats already handled by reconstruction.
- `!data` emits `[event_id] [event_type] name: user (score)`.

Any format change requires a parser that accepts old and new formats plus golden tests
for reconstruction from existing messages.
