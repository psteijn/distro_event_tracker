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

    # Expected format: [event_id] Event Name (multiplier): User1 (score), User2 (score)
    # Multiplier: 1.5
    # pixelpegasus: 1.5 * 1.0 = 1.5
    # micmatty: 1.5 * 0.75 = 1.125 -> 1.13 (approx) or 1.125
    # bloodsworn.: 1.5 * 0.5 = 0.75

    # Note: calculate_event_weighted_scores uses f"{score:.2f}".rstrip('0').rstrip('.')
    # 1.5 * 0.75 = 1.125 -> 1.12 (Python's round half to even)

    expected_line = "[test_event_123] WW Darkmire Contested (1.5x): pixelpegasus (1.5), micmatty (1.12), bloodsworn. (0.75)"
    assert raw_output == expected_line


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

    # Expected: [test_event_456] Boss Fight (2x): manual_user (0.5)
    expected_line = "[test_event_456] Boss Fight (2x): manual_user (0.5)"
    assert raw_output == expected_line
