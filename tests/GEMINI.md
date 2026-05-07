# Testing Instructions for Distro Event Tracker

This file provides specific guidance for working with the test suite in this repository.

## 🎭 Discord Mocking Framework
- **Core Helpers:** Use `MockContext`, `MockMessage`, and `MockGuild` from `tests/utils_discord_mocks.py`.
- **Pattern:** Mock the `ctx` object to verify bot responses without an active Discord connection.
- **Assertion Style:** Use `ctx.send.assert_called_with(...)` or check the `args` of the calls to verify output.

## 🧪 Writing New Tests
- **Decorator:** All async test functions MUST be decorated with `@pytest.mark.asyncio`.
- **Isolation:** 
    - For logic tests (e.g., scoring), test the functions in `main.py` directly by passing mock data.
    - For command tests, use the `event_tracker` instance but ensure it is cleared or controlled between tests.
- **Event Tracker:** When testing commands that rely on history, you may need to manually populate `event_tracker.events` to simulate a "reconstructed" state.

## 🔍 Validation Checklist
1. Does the test cover a "historical" vs "live" event scenario?
2. Are timezones handled correctly using `PACIFIC_TZ`?
3. Does the test verify the final weighted score calculation?
4. If modifying embeds, does the test verify the manual attendance field formatting?
