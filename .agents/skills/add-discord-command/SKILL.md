---
name: add-discord-command
description: Add or modify a Discord command in this repository using a thin adapter and testable feature behavior.
---

# Add Discord Command

1. Implement behavior in the owning feature package without Discord objects.
2. Add the smallest Discord adapter needed for validation and rendering.
3. Preserve command names, aliases, channel gates, and permissions unless requested.
4. Test service behavior and adapter responses using `tests/utils_discord_mocks.py`.
5. Update user help and run the full validation command.
