# Persistence Contracts

Discord message history is the production datastore. These formats are public,
backward-compatible contracts.

- Event embeds use recognized emoji title prefixes.
- Event footers use `Event ID: <id>`.
- Event embeds use `Created by` and `Manual Attendance` field names.
- Dibs state supports the current `https://dibs.data?payload=` format and all legacy
  formats already handled by reconstruction.
- Numbered `⚙️ System Data Block (n/total)` messages form one dibs snapshot;
  reconstruction uses the newest complete snapshot and ignores incomplete replacements.
- Human-readable dibs summaries may span multiple `📦 Current Dibs Summary`
  messages, each bounded to Discord's embed-description limit.
- `!data` emits `[event_id] [event_type] name: user (score)`.
- Planning-card footers use `Planning Data: <base64 JSON>`. Version 1 records retain
  their original start/end instants; records created before the optional `tz` field
  are interpreted as Pacific for later typed scheduling input.

Any format change requires a parser that accepts old and new formats plus golden tests
for reconstruction from existing messages.
