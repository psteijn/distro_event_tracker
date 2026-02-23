import pytest
import main
from main import event_tracker, missing
from tests.utils_discord_mocks import DummyCtx


@pytest.mark.asyncio
async def test_missing_happy_case_no_args():
    """
    When called with no args, !missing compares the last two events:
    users who attended previous event but missed the most recent one.
    """
    event_tracker.events.clear()

    # Previous event (older)
    event_tracker.events["evt_old"] = {
        "id": "evt_old",
        "name": "Old Run",
        "channel_id": 1,
        "message_id": 10,
        "creator_id": 1,
        "created_at": 1000,  # older
        "multiplier": 1.0,
        "attendance": {
            1: ("Alice", [":x:"]),
            2: ("Bob", [":x:"]),
        },
        "manual_attendance": [
            {"name": "Carl", "multiplier": 1.0},
        ],
    }

    # Recent event (newer)
    event_tracker.events["evt_new"] = {
        "id": "evt_new",
        "name": "New Run",
        "channel_id": 1,
        "message_id": 11,
        "creator_id": 1,
        "created_at": 2000,  # newer
        "multiplier": 1.0,
        "attendance": {
            2: ("Bob", [":x:"]),  # Only Bob shows up again
        },
        "manual_attendance": [],
    }

    ctx = DummyCtx()

    # Act: no args → compare last two events
    await missing.callback(ctx)

    # One embed should have been sent
    assert len(ctx.sent) == 1
    embed = ctx.sent[0]["embed"]
    assert embed is not None
    assert embed.title == "👥 Missing Users Report"

    # Find the "Missing Users" field
    missing_field = next((f for f in embed.fields if f.name.startswith("Missing Users")), None)
    assert missing_field is not None

    # Users who attended old but not new: Alice + Carl
    # Order is sorted, so we expect "Alice, Carl"
    value = missing_field.value
    assert "Alice" in value
    assert "Carl" in value
    assert "Bob" not in value

    # Summary field should reflect 2 missing users
    summary_field = next((f for f in embed.fields if f.name == "Summary"), None)
    assert summary_field is not None
    assert "**2** user(s)" in summary_field.value
