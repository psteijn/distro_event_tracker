"""Discord-independent event scoring rules."""

from collections.abc import Mapping
from datetime import datetime, tzinfo
from typing import Any

from ..config import EMOJI_FIFTY, EMOJI_HUNDRED, EMOJI_SEVENTY_FIVE, EMOJI_TWENTY_FIVE

PARTICIPATION_WEIGHTS = {
    EMOJI_HUNDRED: 1.0,
    EMOJI_SEVENTY_FIVE: 0.75,
    EMOJI_FIFTY: 0.5,
    EMOJI_TWENTY_FIVE: 0.25,
}

# Keep aligned with BACKFILL_TYPE_MAP in the Discord adapter.
EVENT_TYPE_MAP = {"🏰": "dungeon", "⚔️": "mini", "🗺️": "t8", "👹": "main", "👑": "omni"}


def emoji_name(emoji: str) -> str:
    if emoji.startswith("<:") and emoji.endswith(">"):
        return emoji.split(":")[1]
    return emoji


def calculate_event_weighted_scores(event: Mapping[str, Any]) -> dict[str, float]:
    """Calculate scores while preserving the existing dictionary wire contract."""
    scores: dict[str, float] = {}
    event_multiplier = float(event.get("multiplier", 1.0))

    for user_name, emojis in event["attendance"].values():
        participation = max(
            (PARTICIPATION_WEIGHTS.get(emoji_name(emoji), 0.0) for emoji in emojis),
            default=0.0,
        )
        scores[user_name] = event_multiplier * participation

    for attendance in event.get("manual_attendance", []):
        if isinstance(attendance, dict):
            scores[str(attendance["name"])] = event_multiplier * float(attendance["multiplier"])

    return dict(sorted(scores.items(), key=lambda item: item[1], reverse=True))


def format_created_at(created_at: float, tz: tzinfo) -> str:
    """Return an event creation time as ISO 8601 with a numeric offset."""
    created = datetime.fromtimestamp(float(created_at), tz=tz)
    return created.isoformat(timespec="seconds")


def format_raw_data_summary(events: list[Mapping[str, Any]], tz: tzinfo) -> list[str]:
    """Format !data records as [id] [created_at] [type] name: user (score)."""
    if not events:
        return ["No events found"]

    return [_format_raw_data_line(event, tz) for event in events]


def _format_raw_data_line(event: Mapping[str, Any], tz: tzinfo) -> str:
    event_type = EVENT_TYPE_MAP.get(str(event.get("type_emoji", "")), "unknown")
    attendees = [
        f"{user_name} ({_format_score(score)})"
        for user_name, score in calculate_event_weighted_scores(event).items()
    ]
    return (
        f"[{event['id']}] [{format_created_at(float(event['created_at']), tz)}] "
        f"[{event_type}] {event['name']}: {', '.join(attendees)}"
    )


def _format_score(score: float) -> str:
    return f"{score:.2f}".rstrip("0").rstrip(".")
