from distro_event_tracker.events.planning_persistence import (
    format_planning_footer,
    parse_planning_footer,
)
from test_planning import make_plan


def test_planning_footer_round_trips_optional_fields_and_schedule():
    plan = make_plan()
    plan.event_type = "Bosses"
    plan.details = "North gate"
    plan.scheduled_start = plan.starts_at
    plan.scheduled_end = plan.ends_at

    restored = parse_planning_footer(format_planning_footer(plan), message_id=99, channel_id=42)

    assert restored is not None
    assert restored.message_id == 99
    assert restored.channel_id == 42
    assert restored.event_type == "Bosses"
    assert restored.minimum_people is None
    assert restored.scheduled_end == plan.ends_at
