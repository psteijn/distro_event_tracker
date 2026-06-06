# Agent Guide

Read `docs/architecture.md` before changing code and
`docs/persistence-contracts.md` before changing embeds, parsing, or raw output.

## Rules

- Discord history remains the datastore; preserve all persistence contracts.
- Put domain behavior in the owning feature package, not `bot.py`.
- Add Discord commands and listeners to the owning feature Cog.
- Keep Discord handlers thin and inject dependencies into testable behavior.
- Do not introduce import-time network access or production mutations.
- Use `send_long_message` for long Discord output.

## Validation

Run focused tests while editing, then run `check.bat` on Windows or `./check.sh`.
Deployment is separate and must only run when explicitly requested.
