"""Pure domain rules for reaction-based event planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable

import pytz

BLOCK_MINUTES = 30
NUMBER_EMOJIS = (
    "1\ufe0f\u20e3",
    "2\ufe0f\u20e3",
    "3\ufe0f\u20e3",
    "4\ufe0f\u20e3",
    "5\ufe0f\u20e3",
    "6\ufe0f\u20e3",
    "7\ufe0f\u20e3",
    "8\ufe0f\u20e3",
)


@dataclass(slots=True, frozen=True)
class PlanBlock:
    start: datetime

    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=BLOCK_MINUTES)


@dataclass(slots=True)
class EventPlan:
    id: str
    message_id: int
    channel_id: int
    leader_id: int
    name: str
    starts_at: datetime
    ends_at: datetime
    event_type: str | None = None
    minimum_people: int | None = None
    maximum_people: int | None = None
    details: str | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    cancelled: bool = False
    availability: dict[int, set[int]] = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        return not self.cancelled and self.scheduled_start is None


def build_blocks(starts_at: datetime, ends_at: datetime) -> list[PlanBlock]:
    """Return half-hour blocks in a valid planning window."""
    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        raise ValueError("Planning times must include a timezone.")
    if starts_at >= ends_at or starts_at.minute not in (0, 30) or ends_at.minute not in (0, 30):
        raise ValueError("Times must be ordered and fall on :00 or :30.")
    blocks: list[PlanBlock] = []
    current = starts_at
    while current < ends_at:
        blocks.append(PlanBlock(current))
        current += timedelta(minutes=BLOCK_MINUTES)
    return blocks


def parse_local_datetime(value: str, timezone: str = "America/Los_Angeles") -> datetime:
    """Parse the slash-command datetime format in the configured local timezone."""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise ValueError("Use YYYY-MM-DD HH:MM, for example 2026-09-12 18:30.") from exc
    if parsed.minute not in (0, 30):
        raise ValueError("Times must fall on :00 or :30.")
    return pytz.timezone(timezone).localize(parsed)


def block_counts(plan: EventPlan, block_count: int) -> list[int]:
    return [
        sum(index in blocks for blocks in plan.availability.values())
        for index in range(block_count)
    ]


def overlapping_users(plan: EventPlan, start_index: int, end_index: int) -> dict[int, set[int]]:
    """Return every voter with at least one selected block in the scheduled period."""
    selected = set(range(start_index, end_index))
    return {
        user_id: indices & selected
        for user_id, indices in plan.availability.items()
        if indices & selected
    }


def whole_event_users(plan: EventPlan, start_index: int, end_index: int) -> set[int]:
    selected = set(range(start_index, end_index))
    return {user_id for user_id, indices in plan.availability.items() if selected <= indices}


def validate_party_size(minimum: int | None, maximum: int | None) -> None:
    if minimum is not None and minimum < 1:
        raise ValueError("Minimum people must be at least 1.")
    if maximum is not None and maximum < 1:
        raise ValueError("Maximum people must be at least 1.")
    if minimum is not None and maximum is not None and maximum < minimum:
        raise ValueError("Maximum people must be at least the minimum.")


def format_periods(blocks: Iterable[int], all_blocks: list[PlanBlock]) -> str:
    """Format selected block indexes as compact contiguous local-time ranges."""
    values = sorted(blocks)
    if not values:
        return "none"
    ranges: list[tuple[int, int]] = []
    first = last = values[0]
    for value in values[1:]:
        if value == last + 1:
            last = value
        else:
            ranges.append((first, last))
            first = last = value
    ranges.append((first, last))
    return ", ".join(
        f"{all_blocks[first].start.strftime('%H:%M')}–{all_blocks[last].end.strftime('%H:%M')}"
        for first, last in ranges
    )
