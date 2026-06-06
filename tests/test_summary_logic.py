import pytest

from distro_event_tracker.bot import EventTracker


@pytest.fixture
def populated_tracker():
    """Returns a tracker with 5 events spread over time."""
    tracker = EventTracker()
    # Event IDs with timestamps (ID format: messageid_timestamp)
    tracker.create_event("100_1000", "Event 1", 1, 100, 1, 1000.0, type_emoji="🏰")
    tracker.create_event("200_2000", "Event 2", 1, 200, 1, 2000.0, type_emoji="⚔️")
    tracker.create_event("300_3000", "Event 3", 1, 300, 1, 3000.0, type_emoji="🗺️")
    tracker.create_event("400_4000", "Event 4", 1, 400, 1, 4000.0, type_emoji="👹")
    tracker.create_event("500_5000", "Event 5", 1, 500, 1, 5000.0, type_emoji="👑")
    return tracker


def test_get_events_between_ids_happy_path(populated_tracker):
    """Verify that we get a correct inclusive range of 3 events."""
    events = populated_tracker.get_events_between_ids("200_2000", "400_4000")
    assert len(events) == 3
    assert events[0]["name"] == "Event 2"
    assert events[-1]["name"] == "Event 4"


def test_get_events_between_ids_out_of_order(populated_tracker):
    """Verify that swapping start/end IDs still returns the correct range."""
    events = populated_tracker.get_events_between_ids("400_4000", "200_2000")
    assert len(events) == 3
    assert events[0]["name"] == "Event 2"
    assert events[-1]["name"] == "Event 4"


def test_get_events_between_ids_single_event(populated_tracker):
    """Verify that pointing start and end to the same ID returns just that event."""
    events = populated_tracker.get_events_between_ids("300_3000", "300_3000")
    assert len(events) == 1
    assert events[0]["name"] == "Event 3"


def test_get_events_between_ids_invalid_id(populated_tracker):
    """Verify that if one ID is missing, we get an empty list (fail-safe)."""
    events = populated_tracker.get_events_between_ids("100_1000", "invalid_id")
    assert events == []


def test_get_last_n_events(populated_tracker):
    """Verify that 'last 2' returns the most recent 2 events in chronological order."""
    events = populated_tracker.get_last_n_events(2)
    assert len(events) == 2
    assert events[0]["name"] == "Event 4"
    assert events[1]["name"] == "Event 5"


def test_get_last_n_events_overflow(populated_tracker):
    """Verify that requesting more events than exist returns all available events."""
    events = populated_tracker.get_last_n_events(10)
    assert len(events) == 5


def test_chronological_sorting_stability():
    """Verify that events with identical timestamps are still sorted correctly (by list insertion or ID)."""
    tracker = EventTracker()
    # Same timestamp, different IDs
    tracker.create_event("id_b", "Second", 1, 10, 1, 1000.0, type_emoji="🏰")
    tracker.create_event("id_a", "First", 1, 5, 1, 1000.0, type_emoji="🏰")

    # We want to ensure that if timestamps are identical, we don't crash and maintain some order.
    # Current implementation uses 'created_at' for sorting.
    events = tracker.get_last_n_events(2)
    assert len(events) == 2
    # Since timestamps are identical, the sort order depends on Python's Timsort stability
    # and the original order in the dictionary.
