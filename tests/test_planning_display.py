from distro_event_tracker.events.planning import build_blocks, parse_local_datetime
from distro_event_tracker.events.planning_display import field_pages, local_availability, time_range
from test_planning import make_plan


def test_time_ranges_always_include_localized_dates_for_both_endpoints():
    plan = make_plan()
    rendered = time_range(plan.starts_at, plan.ends_at)

    assert rendered.count("<t:") == 2
    assert ":f>" in rendered


def test_personal_availability_merges_gaps_with_localized_endpoint_timestamps():
    plan = make_plan()
    rendered = local_availability({0, 1, 3}, build_blocks(plan.starts_at, plan.ends_at))

    assert rendered.count("<t:") == 4
    assert "18:00" not in rendered


def test_field_pages_preserve_row_order_and_discord_field_limit():
    rows = ["a" * 600, "b" * 600, "c" * 10]

    assert field_pages(rows) == [rows[0], f"{rows[1]}\n{rows[2]}"]


def test_equivalent_organizer_times_produce_identical_discord_timestamps():
    pacific = parse_local_datetime("2026-09-11 18:00", "America/Los_Angeles")
    eastern = parse_local_datetime("2026-09-11 21:00", "America/New_York")

    assert pacific == eastern
    assert time_range(pacific, pacific) == time_range(eastern, eastern)
