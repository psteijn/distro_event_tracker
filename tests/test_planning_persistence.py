import base64
import json

from distro_event_tracker.events.planning_cog import PlanningCog
from distro_event_tracker.events.planning_persistence import (
    PLANNING_DATA_PREFIX,
    format_planning_footer,
    parse_planning_card,
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
    assert restored.input_timezone == "America/Los_Angeles"


def test_legacy_planning_footer_defaults_input_timezone_to_pacific():
    plan = make_plan()
    payload = json.loads(
        base64.urlsafe_b64decode(format_planning_footer(plan).removeprefix(PLANNING_DATA_PREFIX))
    )
    del payload["tz"]
    footer = PLANNING_DATA_PREFIX + base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")

    restored = parse_planning_footer(footer, message_id=99, channel_id=42)

    assert restored is not None
    assert restored.starts_at == plan.starts_at
    assert restored.ends_at == plan.ends_at
    assert restored.input_timezone == "America/Los_Angeles"


def test_readable_card_round_trips_without_a_data_footer():
    plan = make_plan()
    plan.id = "AbC123dEf456"
    card = PlanningCog(None, "2")._embed(plan)

    restored = parse_planning_card(card, message_id=99, channel_id=42)

    assert restored is not None
    assert restored.id == plan.id
    assert restored.starts_at == plan.starts_at
    assert restored.ends_at == plan.ends_at
    assert card.footer.text is None
