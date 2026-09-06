"""Discord-history metadata codec for event-planning cards."""

import base64
import binascii
import json
import re
from datetime import datetime

from .planning import EventPlan

PLANNING_DATA_PREFIX = "Planning Data: "
_TIMESTAMP = re.compile(r"<t:(\d+):[a-zA-Z]>")


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


def parse_planning_card(embed, *, message_id: int, channel_id: int) -> EventPlan | None:
    """Parse the readable v2 planning card emitted without a data footer."""
    try:
        state, name = embed.title.split(" · ", 1)
        fields = {field.name: field.value for field in embed.fields}
        plan_id = fields["Plan ID"].strip()
        leader = re.fullmatch(r"<@(\d+)>", fields["Leader"].strip())
        timezone = fields["Input timezone"].strip()
        window = _timestamps(fields["Availability window"])
        scheduled = _timestamps(fields.get("Scheduled time", ""))
        if (
            not plan_id
            or leader is None
            or len(window) != 2
            or state not in {"PLANNING", "SCHEDULED", "CANCELLED"}
        ):
            return None
        party = fields.get("Party size")
        minimum = maximum = None
        if party:
            numbers = [int(value) for value in re.findall(r"\d+", party)]
            if party.startswith("Target:") and len(numbers) == 2:
                minimum, maximum = numbers
            elif party.startswith("Minimum:"):
                minimum = numbers[0]
            elif party.startswith("Preferred maximum:"):
                maximum = numbers[0]
        return EventPlan(
            id=plan_id,
            message_id=message_id,
            channel_id=channel_id,
            leader_id=int(leader.group(1)),
            name=name,
            starts_at=datetime.fromtimestamp(window[0]).astimezone(),
            ends_at=datetime.fromtimestamp(window[1]).astimezone(),
            event_type=fields.get("Type"),
            minimum_people=minimum,
            maximum_people=maximum,
            details=fields.get("Details"),
            scheduled_start=(
                datetime.fromtimestamp(scheduled[0]).astimezone() if scheduled else None
            ),
            scheduled_end=datetime.fromtimestamp(scheduled[1]).astimezone() if scheduled else None,
            cancelled=state == "CANCELLED",
            input_timezone=timezone,
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _timestamps(value: str) -> list[int]:
    return [int(match) for match in _TIMESTAMP.findall(value)]
