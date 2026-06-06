"""Discord-independent event scoring rules."""

from collections.abc import Mapping
from typing import Any

from ..config import EMOJI_FIFTY, EMOJI_HUNDRED, EMOJI_SEVENTY_FIVE, EMOJI_TWENTY_FIVE

PARTICIPATION_WEIGHTS = {
    EMOJI_HUNDRED: 1.0,
    EMOJI_SEVENTY_FIVE: 0.75,
    EMOJI_FIFTY: 0.5,
    EMOJI_TWENTY_FIVE: 0.25,
}


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
