# Testing

Run `check.bat` on Windows or `./check.sh` on shell environments before deployment.
These commands are non-mutating and run formatting checks, Ruff, Mypy, import
contracts, pytest, and coverage.

Prefer pure service tests without Discord objects. For adapter tests, use
`tests/utils_discord_mocks.py`. Persistence changes require round-trip and legacy
fixture coverage. Never use live Discord access in tests.
