from main import EventTracker, EMOJI_HUNDRED, EMOJI_SEVENTY_FIVE, EMOJI_FIFTY


def test_generate_raw_data_summary():
    tracker = EventTracker()

    # Create a test event
    event_id = "test_event_123"
    tracker.create_event(
        event_id=event_id,
        name="WW Darkmire Contested",
        channel_id=1,
        message_id=1,
        creator_id=1,
        created_at=1000.0,
        multiplier=1.5,
    )

    # Add some attendance
    tracker.add_attendance(event_id, 101, "pixelpegasus", EMOJI_HUNDRED)
    tracker.add_attendance(event_id, 102, "bloodsworn.", EMOJI_FIFTY)
    tracker.add_attendance(event_id, 103, "micmatty", EMOJI_SEVENTY_FIVE)

    events = [tracker.events[event_id]]
    raw_output = tracker.generate_raw_data_summary(events)

    # Expected format: [event_id] Event Name (type) (multiplier): User1 (score), User2 (score)
    # type_emoji is empty, so it should be "unknown"
    expected_line = "[test_event_123] WW Darkmire Contested (unknown) (1.5x): pixelpegasus (1.5), micmatty (1.12), bloodsworn. (0.75)"
    assert raw_output == [expected_line]


def test_generate_raw_data_summary_with_type():
    tracker = EventTracker()

    # Create a test event with type emoji
    event_id = "test_event_type"
    tracker.create_event(
        event_id=event_id,
        name="Dungeon Run",
        channel_id=1,
        message_id=1,
        creator_id=1,
        created_at=1000.0,
        multiplier=1.0,
        type_emoji="🏰",
    )

    tracker.add_attendance(event_id, 101, "user1", EMOJI_HUNDRED)

    events = [tracker.events[event_id]]
    raw_output = tracker.generate_raw_data_summary(events)

    expected_line = "[test_event_type] Dungeon Run (dungeon) (1x): user1 (1)"
    assert raw_output == [expected_line]


def test_generate_raw_data_summary_manual_attendance():
    tracker = EventTracker()

    # Create a test event
    event_id = "test_event_456"
    event = tracker.create_event(
        event_id=event_id,
        name="Boss Fight",
        channel_id=1,
        message_id=1,
        creator_id=1,
        created_at=2000.0,
        multiplier=2.0,
    )

    # Add manual attendance
    event['manual_attendance'].append({'name': "manual_user", 'multiplier': 0.25})

    events = [tracker.events[event_id]]
    raw_output = tracker.generate_raw_data_summary(events)

    # Expected: [test_event_456] Boss Fight (unknown) (2x): manual_user (0.5)
    expected_line = "[test_event_456] Boss Fight (unknown) (2x): manual_user (0.5)"
    assert raw_output == [expected_line]
