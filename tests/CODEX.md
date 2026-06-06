# Test Guidance for Distro Event Tracker

This file gives Codex-specific guidance for working on tests in this repository.

## Discord Mocking

- Use the mocks in `tests/utils_discord_mocks.py` for command and message tests.
- Prefer mocked contexts, messages, and guilds over any live Discord access.
- Keep assertions focused on the exact response shape and side effects.

## Writing Tests

- Mark async tests with `@pytest.mark.asyncio`.
- For pure logic, test helpers in `main.py` directly with controlled data.
- For command behavior, exercise the bot-facing function with mock interactions and verify:
  - response text,
  - channel gating,
  - state updates,
  - follow-up refresh behavior.
- If a test depends on reconstructed state, populate the tracker or event store explicitly inside the test.

## Recommended Validation Flow

1. Run the test suite with `.\run_tests.bat` on Windows or `./run_tests.sh` on shell environments.
2. If a test fails, inspect the nearest helper first, then the command wrapper.
3. If the change touches formatting or embeds, verify the output text and field layout directly in the assertion.
4. Keep tests deterministic; avoid timing-sensitive or network-dependent behavior.

## What to Check

- Historical vs live reconstruction behavior.
- Pacific timezone handling.
- Weighted score calculation.
- Manual attendance formatting.
- Dibs and undibs state changes, including clear-all behavior and invalid quantity handling.

