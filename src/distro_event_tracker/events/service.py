"""Discord-independent event state and query service."""

from typing import cast

from .models import Event


def _created_at(event: dict[str, object]) -> float:
    return float(cast(float, event["created_at"]))


class EventService:
    def __init__(self) -> None:
        self.events: dict[str, dict[str, object]] = {}

    def create_event(self, event: Event) -> dict[str, object]:
        stored = event.to_legacy_dict()
        self.events[event.id] = stored
        return stored

    def add_attendance(self, event_id: str, user_id: int, user_name: str, emoji: str) -> bool:
        event = self.events.get(event_id)
        if event is None:
            return False
        attendance = event["attendance"]
        assert isinstance(attendance, dict)
        if user_id not in attendance:
            attendance[user_id] = (user_name, [])
        if emoji not in attendance[user_id][1]:
            attendance[user_id][1].append(emoji)
        return True

    def remove_attendance(self, event_id: str, user_id: int, emoji: str) -> bool:
        event = self.events.get(event_id)
        if event is None:
            return False
        attendance = event["attendance"]
        assert isinstance(attendance, dict)
        if user_id not in attendance:
            return False
        if emoji in attendance[user_id][1]:
            attendance[user_id][1].remove(emoji)
            if not attendance[user_id][1]:
                del attendance[user_id]
        return True

    def events_in_range(self, start: int, end: int) -> list[dict[str, object]]:
        return sorted(
            (event for event in self.events.values() if start <= _created_at(event) <= end),
            key=_created_at,
        )

    def events_between_ids(self, start_id: str, end_id: str) -> list[dict[str, object]]:
        ordered = sorted(self.events.values(), key=_created_at)
        ids = [str(event["id"]) for event in ordered]
        if start_id not in ids or end_id not in ids:
            return []
        start, end = sorted((ids.index(start_id), ids.index(end_id)))
        return ordered[start : end + 1]

    def last_events(self, count: int) -> list[dict[str, object]]:
        ordered = sorted(self.events.values(), key=_created_at, reverse=True)
        return sorted(ordered[:count], key=_created_at)

    def most_recent_before(self, event_id: str) -> dict[str, object] | None:
        target = self.events.get(event_id)
        if target is None:
            return None
        target_time = _created_at(target)
        candidates = [event for event in self.events.values() if _created_at(event) < target_time]
        return max(candidates, key=_created_at, default=None)
