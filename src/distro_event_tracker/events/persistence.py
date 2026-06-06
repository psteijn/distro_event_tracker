"""Stable event persistence contract constants and parsing helpers."""

EVENT_ID_PREFIX = "Event ID: "
CREATED_BY_FIELD = "Created by"
MANUAL_ATTENDANCE_FIELD = "Manual Attendance"


def format_event_footer(event_id: str) -> str:
    return f"{EVENT_ID_PREFIX}{event_id}"


def parse_event_footer(footer: str | None) -> str | None:
    if footer and footer.startswith(EVENT_ID_PREFIX):
        return footer.removeprefix(EVENT_ID_PREFIX)
    return None
