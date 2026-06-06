from distro_event_tracker.bot import calculate_event_weighted_scores
from distro_event_tracker.config import (
    EMOJI_FIFTY,
    EMOJI_HUNDRED,
    EMOJI_SEVENTY_FIVE,
    EMOJI_TWENTY_FIVE,
)


def make_base_event():
    return {
        "id": "event1",
        "name": "Test Event",
        "type_emoji": "🏰",
        "channel_id": 123,
        "message_id": 456,
        "creator_id": 789,
        "created_at": 1_700_000_000,
        "multiplier": 1.0,
        "attendance": {},
        "manual_attendance": [],
    }


def test_weighted_scores_no_attendance():
    event = make_base_event()
    scores = calculate_event_weighted_scores(event)
    assert scores == {}


def test_weighted_scores_highest_emoji_wins():
    event = make_base_event()
    event["attendance"] = {
        123: ("Alice", [EMOJI_TWENTY_FIVE, EMOJI_FIFTY, EMOJI_HUNDRED]),
    }
    scores = calculate_event_weighted_scores(event)
    assert scores == {"Alice": 1.0}


def test_weighted_scores_custom_emoji_parsing():
    event = make_base_event()
    custom_emoji_str = f"<:{EMOJI_SEVENTY_FIVE}:1234567890>"
    event["attendance"] = {
        123: ("Alice", [custom_emoji_str]),
    }
    scores = calculate_event_weighted_scores(event)
    assert scores == {"Alice": 0.75}


def test_weighted_scores_applies_event_multiplier():
    event = make_base_event()
    event["multiplier"] = 2.0
    event["attendance"] = {
        123: ("Alice", [EMOJI_FIFTY]),  # 0.5 * 2.0 -> 1.0
    }
    scores = calculate_event_weighted_scores(event)
    assert scores == {"Alice": 1.0}


def test_weighted_scores_manual_attendance_included():
    event = make_base_event()
    event["attendance"] = {
        1: ("Alice", [EMOJI_HUNDRED]),
    }
    event["manual_attendance"] = [
        {"name": "Bob", "multiplier": 0.5},
    ]
    scores = calculate_event_weighted_scores(event)
    assert scores == {"Alice": 1.0, "Bob": 0.5}


def test_weighted_scores_sorted_descending():
    event = make_base_event()
    event["attendance"] = {
        1: ("Alice", [EMOJI_HUNDRED]),  # 1.0
        2: ("Bob", [EMOJI_FIFTY]),  # 0.5
    }
    event["manual_attendance"] = [
        {"name": "Charlie", "multiplier": 0.75},
    ]
    scores = calculate_event_weighted_scores(event)
    # Ensure keys are in descending order of score
    assert list(scores.keys()) == ["Alice", "Charlie", "Bob"]
