---
name: change-event-tracker
description: Modify event tracking, attendance, scoring, summaries, or event commands in this repository while preserving Discord persistence contracts.
---

# Change Event Tracker

1. Read `docs/architecture.md` and the relevant event modules.
2. Read `docs/persistence-contracts.md` when output or reconstruction may change.
3. Put rules in `src/distro_event_tracker/events`; keep Discord handlers thin.
4. Add focused pure tests, then adapter tests when Discord behavior changes.
5. Run the focused tests and finish with `check.bat` or `./check.sh`.
