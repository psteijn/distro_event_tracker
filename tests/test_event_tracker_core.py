from distro_event_tracker.bot import EventTracker
from distro_event_tracker.config import EMOJI_FIFTY, EMOJI_HUNDRED, EMOJI_SEVENTY_FIVE


def setup_event_with_tracker():
    tracker = EventTracker()
    tracker.create_event(
        "evt1",
        "Test Event",
        channel_id=1,
        message_id=2,
        creator_id=3,
        created_at=100.0,
        multiplier=1.0,
        type_emoji="🏰",
    )
    return tracker


def test_create_event_initializes_fields():
    tracker = EventTracker()
    event = tracker.create_event(
        event_id="evt1",
        name="Test Event",
        type_emoji="🏰",
        channel_id=123,
        message_id=456,
        creator_id=789,
        created_at=100.0,
        multiplier=2.0,
        is_historical=False,
    )
    assert "evt1" in tracker.events
    assert event["name"] == "Test Event"
    assert event["type_emoji"] == "🏰"
    assert event["multiplier"] == 2.0
    assert event["attendance"] == {}
    assert event["manual_attendance"] == []
    assert event["created_at"] == 100.0
    assert event["is_historical"] is False


def test_add_attendance_new_user():
    tracker = setup_event_with_tracker()
    tracker.add_attendance("evt1", 123, "Alice", "E1")
    event = tracker.events["evt1"]
    assert 123 in event["attendance"]
    assert event["attendance"][123][0] == "Alice"
    assert event["attendance"][123][1] == ["E1"]


def test_add_attendance_does_not_duplicate_emoji():
    tracker = setup_event_with_tracker()
    tracker.add_attendance("evt1", 123, "Alice", "E1")
    tracker.add_attendance("evt1", 123, "Alice", "E1")
    event = tracker.events["evt1"]
    assert event["attendance"][123][1] == ["E1"]  # no duplicate


def test_remove_attendance_removes_emoji_and_user():
    tracker = setup_event_with_tracker()
    tracker.add_attendance("evt1", 123, "Alice", "E1")
    tracker.remove_attendance("evt1", 123, "Alice", "E1")
    event = tracker.events["evt1"]
    assert 123 not in event["attendance"]


def test_get_events_in_range_filters_by_created_at():
    tracker = EventTracker()
    tracker.create_event("evt1", "Old", 1, 2, 3, 10.0, type_emoji="🏰")
    tracker.create_event("evt2", "Mid", 1, 2, 3, 20.0, type_emoji="🏰")
    tracker.create_event("evt3", "New", 1, 2, 3, 30.0, type_emoji="🏰")

    events = tracker.get_events_in_range(15, 30)
    ids = {e["id"] for e in events}
    assert ids == {"evt2", "evt3"}


def test_generate_summary_merges_manual_attendance(monkeypatch):
    tracker = EventTracker()
    e = tracker.create_event("evt1", "Test", 1, 2, 3, 100.0, type_emoji="🏰")
    e["attendance"] = {123: ("Alice", ["X"])}
    e["manual_attendance"] = [{"name": "Bob", "multiplier": 0.75}]

    summary = tracker.generate_summary([e])
    assert summary["total_events"] == 1
    evt_summary = summary["events"][0]
    assert evt_summary["total_attendees"] == 2, (
        "Expected exactly 2 attendees, but summary contained:\n"
        f"{evt_summary}\n"
        f"attendance_by_user={evt_summary.get('attendance_by_user')}\n"
    )

    attendance_by_user = evt_summary["attendance_by_user"]
    # Existing attendee should be preserved
    assert 123 in attendance_by_user
    # Manual attendee should be merged in by name as a key
    manual_entry = attendance_by_user["Bob"]
    assert manual_entry[0] == "Bob"
    assert len(manual_entry[1]) == 1


def test_calculate_weighted_average_across_events():
    tracker = EventTracker()
    events = [
        {
            "multiplier": 1.0,
            "attendance_by_user": {
                1: ("Alice", [EMOJI_HUNDRED]),  # 1.0
                2: ("Bob", [EMOJI_FIFTY]),  # 0.5
            },
        },
        {
            "multiplier": 2.0,
            "attendance_by_user": {
                1: ("Alice", [EMOJI_SEVENTY_FIVE]),  # 0.75 * 2.0 = 1.5
            },
        },
    ]
    result = tracker.calculate_weighted_average(events)
    # Alice: 1.0 + 1.5 = 2.5
    # Bob: 0.5
    assert "Alice (2.5)" in result
    assert "Bob (0.5)" in result
    # Alice should come before Bob
    alice_idx = result.index("Alice")
    bob_idx = result.index("Bob")
    assert alice_idx < bob_idx


def test_calculate_weighted_average_no_events():
    tracker = EventTracker()
    result = tracker.calculate_weighted_average([])
    assert result == "No events to analyze"


def test_calculate_weighted_average_no_attendees():
    tracker = EventTracker()
    events = [
        {
            "multiplier": 1.0,
            "attendance_by_user": {},
        }
    ]
    result = tracker.calculate_weighted_average(events)
    assert result == "No attendees found"
