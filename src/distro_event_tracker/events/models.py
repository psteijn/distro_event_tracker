"""Typed event domain models.

Discord persistence still uses dictionaries at its boundary. These models make
the in-process contract explicit while compatibility codecs are migrated.
"""

from dataclasses import dataclass, field
from typing import TypeAlias

Attendance: TypeAlias = dict[int, tuple[str, list[str]]]


@dataclass(slots=True)
class ManualAttendance:
    name: str
    multiplier: float

    def to_legacy_dict(self) -> dict[str, object]:
        return {"name": self.name, "multiplier": self.multiplier}


@dataclass(slots=True)
class Event:
    id: str
    name: str
    channel_id: int
    message_id: int
    creator_id: int
    created_at: float
    multiplier: float = 1.0
    type_emoji: str = ""
    is_historical: bool = False
    attendance: Attendance = field(default_factory=dict)
    manual_attendance: list[ManualAttendance] = field(default_factory=list)

    def to_legacy_dict(self) -> dict[str, object]:
        """Return the stable dictionary contract used by Discord adapters."""
        return {
            "id": self.id,
            "name": self.name,
            "type_emoji": self.type_emoji,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "creator_id": self.creator_id,
            "created_at": self.created_at,
            "multiplier": self.multiplier,
            "attendance": self.attendance,
            "manual_attendance": [
                attendance.to_legacy_dict() for attendance in self.manual_attendance
            ],
            "is_historical": self.is_historical,
        }
