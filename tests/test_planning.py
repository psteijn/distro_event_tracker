from datetime import datetime, timezone

import pytest

from distro_event_tracker.events.planning import (
    EventPlan,
    availability_periods,
    block_counts,
    build_blocks,
    format_periods,
    overlapping_users,
    schedule_indices,
    schedule_slot_indices,
    validate_party_size,
    whole_event_users,
)
from distro_event_tracker.events.planning_service import PlanningService


def make_plan():
    tz = timezone.utc
    return EventPlan(
        id="plan",
        message_id=1,
        channel_id=2,
        leader_id=3,
        name="Bosses",
        starts_at=datetime(2026, 9, 12, 18, 0, tzinfo=tz),
        ends_at=datetime(2026, 9, 12, 20, 0, tzinfo=tz),
    )


def test_availability_counts_and_overlapping_recipients():
    plan = make_plan()
    plan.availability = {10: {0, 1, 2}, 11: {1, 2, 3}, 12: {0, 3}}

    assert block_counts(plan, 4) == [2, 2, 2, 2]
    assert whole_event_users(plan, 1, 3) == {10, 11}
    assert overlapping_users(plan, 1, 3) == {10: {1, 2}, 11: {1, 2}}


def test_removing_last_reaction_withdraws_member():
    plan = make_plan()
    service = PlanningService()
    service.add(plan)

    assert service.update_reaction(1, 10, 0, True)
    assert service.update_reaction(1, 10, 0, False)
    assert plan.availability == {}


def test_default_plan_is_newest_open_plan_led_by_caller_and_ids_ignore_case():
    service = PlanningService()
    older = make_plan()
    older.id = "OlderPlan123"
    newer = make_plan()
    newer.id, newer.message_id = "NewerPlan456", 2
    other = make_plan()
    other.message_id, other.leader_id = 3, 4
    service.add(older)
    service.add(newer)
    service.add(other)

    assert service.find_open(leader_id=3) is newer
    assert service.find_open(plan_id=" newerplan456 ") is newer
    newer.cancelled = True
    assert service.find_open(leader_id=3) is older
    assert service.find_open(plan_id="newerplan456") is newer


def test_blocks_require_half_hour_ordered_range():
    plan = make_plan()
    assert len(build_blocks(plan.starts_at, plan.ends_at)) == 4
    with pytest.raises(ValueError):
        build_blocks(plan.ends_at, plan.starts_at)


def test_format_periods_preserves_gaps():
    blocks = build_blocks(make_plan().starts_at, make_plan().ends_at)
    assert format_periods({0, 1, 3}, blocks) == "18:00–19:00, 19:30–20:00"


def test_optional_party_sizes_are_valid_and_checked_when_present():
    validate_party_size(None, None)
    validate_party_size(5, None)
    validate_party_size(None, 10)
    with pytest.raises(ValueError):
        validate_party_size(10, 5)


def test_schedule_uses_an_exclusive_end_index_including_final_block():
    plan = make_plan()
    blocks = build_blocks(plan.starts_at, plan.ends_at)
    start, end = schedule_indices(plan, blocks[-1].start, blocks[-1].end)

    assert (start, end) == (3, 4)
    plan.availability = {10: {3}, 11: {2}}
    assert overlapping_users(plan, start, end) == {10: {3}}
    assert whole_event_users(plan, start, end) == {10}


def test_schedule_slots_are_one_based_and_inclusive():
    plan = make_plan()
    assert schedule_slot_indices(plan, 3, 3) == (2, 3)
    assert schedule_slot_indices(plan, 1, 4) == (0, 4)
    with pytest.raises(ValueError):
        schedule_slot_indices(plan, 4, 3)
    with pytest.raises(ValueError):
        schedule_slot_indices(plan, 0, 1)


def test_availability_periods_merge_adjacent_blocks_but_preserve_gaps():
    blocks = build_blocks(make_plan().starts_at, make_plan().ends_at)

    assert availability_periods({0, 1, 3}, blocks) == [
        (blocks[0].start, blocks[1].end),
        (blocks[3].start, blocks[3].end),
    ]
