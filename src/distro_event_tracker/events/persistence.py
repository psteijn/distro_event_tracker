"""Stable event persistence contract constants and parsing helpers."""

import re

EVENT_ID_PREFIX = "Event ID: "
CREATED_BY_FIELD = "Created by"
MANUAL_ATTENDANCE_FIELD = "Manual Attendance"
LEGACY_BACKFILL_CREATOR_FIELD = "Original Creator"
BACKFILL_EVENT_ID_PREFIX = "bf_"
BACKFILL_TITLE_SUFFIX = " (Backfilled)"

_USER_MENTION_RE = re.compile(r"^<@!?(\d+)>$")


def format_event_footer(event_id: str) -> str:
    return f"{EVENT_ID_PREFIX}{event_id}"


def parse_event_footer(footer: str | None) -> str | None:
    if footer and footer.startswith(EVENT_ID_PREFIX):
        return footer.removeprefix(EVENT_ID_PREFIX)
    return None


def parse_event_creator_id(field_name: str, field_value: str) -> int | None:
    """Read the creator from current and legacy event embed fields."""
    if field_name not in {CREATED_BY_FIELD, LEGACY_BACKFILL_CREATOR_FIELD}:
        return None
    match = _USER_MENTION_RE.fullmatch(field_value)
    return int(match.group(1)) if match else None


def is_backfill_event_id(event_id: str) -> bool:
    return event_id.startswith(BACKFILL_EVENT_ID_PREFIX)


def normalize_reconstructed_event_name(event_id: str, event_name: str) -> str:
    """Remove display-only backfill wording from persisted backfill titles."""
    if is_backfill_event_id(event_id):
        return event_name.removesuffix(BACKFILL_TITLE_SUFFIX)
    return event_name
