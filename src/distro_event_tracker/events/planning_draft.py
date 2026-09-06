"""Discord-independent day/time choices and draft validation."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

import pytz

from .planning import (
    MAX_PLAN_BLOCKS,
    EventPlan,
    build_blocks,
    parse_local_datetime,
    validate_party_size,
)

TIMEZONES = {
    "America/Los_Angeles": "Pacific",
    "America/Denver": "Mountain",
    "America/Phoenix": "Arizona",
    "America/Chicago": "Central",
    "America/New_York": "Eastern",
    "America/Anchorage": "Alaska",
    "Pacific/Honolulu": "Hawaii",
    "UTC": "UTC",
    "Europe/London": "UK/Ireland",
    "Europe/Berlin": "Central Europe",
    "Europe/Helsinki": "Eastern Europe",
    "Asia/Kolkata": "India",
    "Asia/Singapore": "Singapore/China",
    "Asia/Tokyo": "Japan/Korea",
    "Australia/Perth": "Perth",
    "Australia/Adelaide": "Adelaide",
    "Australia/Sydney": "Sydney/Melbourne",
    "Pacific/Auckland": "New Zealand",
}


def day_choices(zone: str, now: datetime) -> list[tuple[date, str]]:
    today = now.astimezone(pytz.timezone(zone)).date()
    choices = []
    for offset in range(15):
        day = today + timedelta(days=offset)
        prefix = "Today · " if offset == 0 else "Tomorrow · " if offset == 1 else ""
        choices.append((day, prefix + day.strftime("%A, %B %d, %Y")))
    return choices


def unique_local(instant: datetime, zone: str) -> bool:
    local = instant.astimezone(pytz.timezone(zone))
    try:
        pytz.timezone(zone).localize(local.replace(tzinfo=None), is_dst=None)
    except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
        return False
    return True


def ending_choices(start: datetime, zone: str) -> list[datetime]:
    """Return up to ten elapsed hours of valid half-hour endings."""
    values = []
    for count in range(1, MAX_PLAN_BLOCKS + 1):
        end = start.astimezone(timezone.utc) + timedelta(minutes=30 * count)
        if unique_local(end, zone):
            values.append(end)
    return values


def starting_choices(day: date, zone: str, now: datetime) -> list[datetime]:
    if day not in {value for value, _ in day_choices(zone, now)}:
        return []
    values = []
    for index in range(48):
        local = datetime.combine(day, time(index // 2, index % 2 * 30))
        try:
            start = parse_local_datetime(local.strftime("%Y-%m-%d %H:%M"), zone)
        except ValueError:
            continue
        if start > now and ending_choices(start, zone):
            values.append(start)
    return values


@dataclass
class PlanningDraft:
    leader_id: int
    channel_id: int
    name: str
    event_type: str | None = None
    minimum_people: int | None = None
    maximum_people: int | None = None
    details: str | None = None
    input_timezone: str = "America/Los_Angeles"
    day: date | None = None
    start: datetime | None = None
    end: datetime | None = None

    def validate_details(self) -> None:
        if not self.name or len(self.name) > 200:
            raise ValueError("Please use an event name between 1 and 200 characters.")
        if self.event_type and len(self.event_type) > 100:
            raise ValueError("Please keep the event type within 100 characters.")
        if self.details and len(self.details) > 1024:
            raise ValueError("Please keep details within 1,024 characters.")
        validate_party_size(self.minimum_people, self.maximum_people)

    def validate_times(self, now: datetime) -> None:
        if self.day is None or self.start is None or self.end is None:
            raise ValueError("Choose a day, beginning, and ending first.")
        if self.start not in starting_choices(self.day, self.input_timezone, now):
            raise ValueError(
                "That beginning is no longer available. Please choose your times again."
            )
        if self.end not in ending_choices(self.start, self.input_timezone):
            raise ValueError("Choose an ending within ten hours.")
        build_blocks(self.start, self.end)

    def to_plan(self, plan_id: str) -> EventPlan:
        if self.start is None or self.end is None:
            raise ValueError("Choose times first.")
        return EventPlan(
            id=plan_id,
            message_id=0,
            channel_id=self.channel_id,
            leader_id=self.leader_id,
            name=self.name,
            starts_at=self.start,
            ends_at=self.end,
            event_type=self.event_type,
            minimum_people=self.minimum_people,
            maximum_people=self.maximum_people,
            details=self.details,
            input_timezone=self.input_timezone,
        )
