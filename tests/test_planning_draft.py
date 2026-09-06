from datetime import datetime, timezone

import pytest
import pytz

from distro_event_tracker.events.planning import parse_local_datetime
from distro_event_tracker.events.planning_draft import day_choices, ending_choices, starting_choices


def test_day_choices_include_today_and_next_fourteen_days_across_month_boundary():
    now = datetime(2026, 1, 31, 23, 30, tzinfo=timezone.utc)
    choices = day_choices("America/Los_Angeles", now)

    assert len(choices) == 15
    assert choices[0][1].startswith("Today · ")
    assert choices[1][1].startswith("Tomorrow · ")
    assert choices[0][0].isoformat() == "2026-01-31"
    assert choices[-1][0].isoformat() == "2026-02-14"


def test_time_choices_are_actual_half_hour_intervals_bounded_by_midnight_and_four_hours():
    start = parse_local_datetime("2026-09-12 22:00", "America/Los_Angeles")
    ends = ending_choices(start, "America/Los_Angeles")

    assert [
        end.astimezone(pytz.timezone("America/Los_Angeles")).strftime("%H:%M") for end in ends
    ] == [
        "22:30",
        "23:00",
        "23:30",
        "00:00",
    ]
    assert all((end - start).total_seconds() <= 4 * 60 * 60 for end in ends)


def test_nonexistent_and_ambiguous_daylight_saving_times_are_not_selectable():
    with pytest.raises(ValueError, match="skipped or repeated"):
        parse_local_datetime("2026-03-08 02:30", "America/Los_Angeles")
    with pytest.raises(ValueError, match="skipped or repeated"):
        parse_local_datetime("2026-11-01 01:30", "America/Los_Angeles")

    now = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
    choices = starting_choices(
        day_choices("America/Los_Angeles", now)[7][0], "America/Los_Angeles", now
    )
    assert all(
        value.astimezone(pytz.timezone("America/Los_Angeles")).hour != 1 for value in choices
    )
