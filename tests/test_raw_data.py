import re
from datetime import datetime

import pytest
import pytz

from distro_event_tracker.bot import EMOJI_FIFTY, EMOJI_HUNDRED, EMOJI_SEVENTY_FIVE, EventTracker
from distro_event_tracker.config import EMOJI_TWENTY_FIVE
from distro_event_tracker.events.scoring import (
    EVENT_TYPE_MAP,
    format_created_at,
    format_raw_data_summary,
)

PACIFIC_TZ = pytz.timezone("US/Pacific")

RAW_DATA_LINE = re.compile(
    r"^\[(?P<id>[^\]]+)\] "
    r"\[(?P<created_at>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2})\] "
    r"\[(?P<event_type>[^\]]+)\] "
    r"(?P<name>.*?): (?P<attendees>.*)$"
)

# Sunday 2026-10-04 20:00 Pacific is Monday 03:00 UTC.
SUNDAY_EVENING_PACIFIC = 1791169200.0
SUNDAY_EVENING_ISO = "2026-10-04T20:00:00-07:00"
# Sunday 2026-01-04 18:00 Pacific is standard time.
WINTER_SUNDAY_PACIFIC = 1767578400.0
WINTER_SUNDAY_ISO = "2026-01-04T18:00:00-08:00"
# The repeated 01:30 on the November fallback, before and after the offset change.
FALL_BACK_PDT = 1793521800.0
FALL_BACK_PDT_ISO = "2026-11-01T01:30:00-07:00"
FALL_BACK_PST = 1793525400.0
FALL_BACK_PST_ISO = "2026-11-01T01:30:00-08:00"
SPRING_PST = 1772962200.0
SPRING_PST_ISO = "2026-03-08T01:30:00-08:00"


def _event(**overrides):
    event = {
        "id": "1554666241732513944_1790731716",
        "name": "Sunday Bosses",
        "type_emoji": "🗺️",
        "created_at": SUNDAY_EVENING_PACIFIC,
        "multiplier": 1.0,
        "attendance": {},
        "manual_attendance": [],
    }
    event.update(overrides)
    return event


def test_generate_raw_data_summary():
    tracker = EventTracker()

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

    tracker.add_attendance(event_id, 101, "pixelpegasus", EMOJI_HUNDRED)
    tracker.add_attendance(event_id, 102, "bloodsworn.", EMOJI_FIFTY)
    tracker.add_attendance(event_id, 103, "micmatty", EMOJI_SEVENTY_FIVE)

    raw_output = tracker.generate_raw_data_summary([tracker.events[event_id]])

    expected_line = (
        "[test_event_123] [1969-12-31T16:16:40-08:00] [unknown] "
        "WW Darkmire Contested: pixelpegasus (1.5), micmatty (1.12), bloodsworn. (0.75)"
    )
    assert raw_output == [expected_line]


def test_generate_raw_data_summary_with_type():
    tracker = EventTracker()

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

    raw_output = tracker.generate_raw_data_summary([tracker.events[event_id]])

    expected_line = "[test_event_type] [1969-12-31T16:16:40-08:00] [dungeon] Dungeon Run: user1 (1)"
    assert raw_output == [expected_line]


def test_generate_raw_data_summary_manual_attendance():
    tracker = EventTracker()

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

    event["manual_attendance"].append({"name": "manual_user", "multiplier": 0.25})

    raw_output = tracker.generate_raw_data_summary([tracker.events[event_id]])

    expected_line = (
        "[test_event_456] [1969-12-31T16:33:20-08:00] [unknown] Boss Fight: manual_user (0.5)"
    )
    assert raw_output == [expected_line]


def test_generate_raw_data_summary_uses_domain_formatter():
    tracker = EventTracker()
    tracker.create_event(
        event_id="tracker_event",
        name="Sunday Bosses",
        channel_id=1,
        message_id=1,
        creator_id=1,
        created_at=SUNDAY_EVENING_PACIFIC,
        multiplier=2.0,
        type_emoji="👹",
    )
    tracker.add_attendance("tracker_event", 101, "alice", EMOJI_HUNDRED)

    events = [tracker.events["tracker_event"]]
    assert tracker.generate_raw_data_summary(events) == format_raw_data_summary(events, PACIFIC_TZ)


def test_raw_data_line_matches_documented_shape():
    line = format_raw_data_summary([_event()], PACIFIC_TZ)[0]
    match = RAW_DATA_LINE.fullmatch(line)

    assert match is not None
    assert match.group("id") == "1554666241732513944_1790731716"
    assert match.group("created_at") == SUNDAY_EVENING_ISO
    assert match.group("event_type") == "t8"
    assert match.group("name") == "Sunday Bosses"
    assert match.group("attendees") == ""


def test_raw_data_timestamp_uses_pacific_calendar_day():
    line = format_raw_data_summary(
        [_event(attendance={1: ("alice", [EMOJI_HUNDRED])}, multiplier=2.0)],
        PACIFIC_TZ,
    )[0]
    match = RAW_DATA_LINE.fullmatch(line)

    assert match is not None
    created_at = datetime.fromisoformat(match.group("created_at"))
    assert match.group("created_at") == SUNDAY_EVENING_ISO
    assert created_at.strftime("%A") == "Sunday"
    assert abs(created_at.timestamp() - SUNDAY_EVENING_PACIFIC) < 1
    assert line.endswith("alice (2)")


def test_raw_data_timestamp_follows_the_supplied_timezone():
    line = format_raw_data_summary([_event()], pytz.UTC)[0]
    assert "[2026-10-05T03:00:00+00:00]" in line
    created_at = datetime.fromisoformat("2026-10-05T03:00:00+00:00")
    assert created_at.strftime("%A") == "Monday"
    assert abs(created_at.timestamp() - SUNDAY_EVENING_PACIFIC) < 1


@pytest.mark.parametrize(
    ("created_at", "expected_iso"),
    [
        (WINTER_SUNDAY_PACIFIC, WINTER_SUNDAY_ISO),
        (SUNDAY_EVENING_PACIFIC, SUNDAY_EVENING_ISO),
        (FALL_BACK_PDT, FALL_BACK_PDT_ISO),
        (FALL_BACK_PST, FALL_BACK_PST_ISO),
        (SPRING_PST, SPRING_PST_ISO),
        (int(SUNDAY_EVENING_PACIFIC), SUNDAY_EVENING_ISO),
        (SUNDAY_EVENING_PACIFIC + 0.9, SUNDAY_EVENING_ISO),
    ],
)
def test_format_created_at_iso_8601_offsets(created_at, expected_iso):
    assert format_created_at(created_at, PACIFIC_TZ) == expected_iso


def test_fractional_created_at_does_not_round_up_inside_a_record():
    line = format_raw_data_summary([_event(created_at=SUNDAY_EVENING_PACIFIC + 0.9)], PACIFIC_TZ)[0]
    assert f"[{SUNDAY_EVENING_ISO}]" in line
    assert "20:00:01" not in line


@pytest.mark.parametrize(("emoji", "event_type"), list(EVENT_TYPE_MAP.items()))
def test_raw_data_includes_every_event_type(emoji, event_type):
    line = format_raw_data_summary([_event(type_emoji=emoji)], PACIFIC_TZ)[0]
    assert f"[{SUNDAY_EVENING_ISO}] [{event_type}] " in line


@pytest.mark.parametrize("type_emoji", ["", "❓", None])
def test_raw_data_unknown_event_type(type_emoji):
    event = _event()
    if type_emoji is None:
        del event["type_emoji"]
    else:
        event["type_emoji"] = type_emoji

    line = format_raw_data_summary([event], PACIFIC_TZ)[0]
    assert f"[{SUNDAY_EVENING_ISO}] [unknown] " in line


def test_raw_data_sorts_attendees_by_score_and_strips_trailing_zeros():
    event = _event(
        multiplier=2.0,
        attendance={
            1: ("low", [EMOJI_TWENTY_FIVE]),
            2: ("high", [EMOJI_HUNDRED]),
            3: ("mid", [f"<:{EMOJI_FIFTY}:99>"]),
        },
        manual_attendance=[{"name": "manual", "multiplier": 0.75}],
    )

    line = format_raw_data_summary([event], PACIFIC_TZ)[0]
    assert line.endswith("high (2), manual (1.5), mid (1), low (0.5)")


def test_raw_data_empty_attendance_keeps_name_separator():
    line = format_raw_data_summary([_event(name="Empty Scan")], PACIFIC_TZ)[0]
    assert line.endswith("[t8] Empty Scan: ")


def test_raw_data_no_events():
    assert format_raw_data_summary([], PACIFIC_TZ) == ["No events found"]


def test_raw_data_preserves_event_order_and_distinct_timestamps():
    events = [
        _event(id="earlier", name="First", created_at=WINTER_SUNDAY_PACIFIC, type_emoji="🏰"),
        _event(id="later", name="Second", created_at=SUNDAY_EVENING_PACIFIC, type_emoji="👑"),
    ]

    assert format_raw_data_summary(events, PACIFIC_TZ) == [
        f"[earlier] [{WINTER_SUNDAY_ISO}] [dungeon] First: ",
        f"[later] [{SUNDAY_EVENING_ISO}] [omni] Second: ",
    ]
