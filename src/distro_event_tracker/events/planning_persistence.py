"""Discord-history metadata codec for event-planning cards."""

import base64
import binascii
import json
from datetime import datetime

from .planning import EventPlan

PLANNING_DATA_PREFIX = "Planning Data: "


def format_planning_footer(plan: EventPlan) -> str:
    """Encode the plan definition in the card footer for restart reconstruction."""
    payload = {
        "v": 1,
        "id": plan.id,
        "l": plan.leader_id,
        "n": plan.name,
        "s": plan.starts_at.isoformat(),
        "e": plan.ends_at.isoformat(),
        "t": plan.event_type,
        "min": plan.minimum_people,
        "max": plan.maximum_people,
        "d": plan.details,
        "ss": plan.scheduled_start.isoformat() if plan.scheduled_start else None,
        "se": plan.scheduled_end.isoformat() if plan.scheduled_end else None,
        "c": plan.cancelled,
        "tz": plan.input_timezone,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    return f"{PLANNING_DATA_PREFIX}{encoded}"


def parse_planning_footer(
    footer: str | None, *, message_id: int, channel_id: int
) -> EventPlan | None:
    if not footer or not footer.startswith(PLANNING_DATA_PREFIX):
        return None
    try:
        encoded = footer.removeprefix(PLANNING_DATA_PREFIX)
        payload = json.loads(base64.urlsafe_b64decode(encoded).decode("utf-8"))
        if payload["v"] != 1:
            return None
        return EventPlan(
            id=payload["id"],
            message_id=message_id,
            channel_id=channel_id,
            leader_id=payload["l"],
            name=payload["n"],
            starts_at=datetime.fromisoformat(payload["s"]),
            ends_at=datetime.fromisoformat(payload["e"]),
            event_type=payload["t"],
            minimum_people=payload["min"],
            maximum_people=payload["max"],
            details=payload["d"],
            scheduled_start=datetime.fromisoformat(payload["ss"]) if payload["ss"] else None,
            scheduled_end=datetime.fromisoformat(payload["se"]) if payload["se"] else None,
            cancelled=payload["c"],
            input_timezone=payload.get("tz", "America/Los_Angeles"),
        )
    except (binascii.Error, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
