---
name: change-discord-persistence
description: Safely change Discord embed or message persistence and reconstruction formats for events or dibs in this repository.
---

# Change Discord Persistence

1. Read `docs/persistence-contracts.md`.
2. Treat existing message formats as immutable input contracts.
3. Add parsing support before emitting a new format.
4. Add golden tests for current, legacy, malformed, and round-trip inputs.
5. Run the full non-mutating validation command. Do not deploy automatically.
