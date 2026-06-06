"""Timezone helpers."""

from datetime import datetime
from zoneinfo import ZoneInfo

PACIFIC_TZ = ZoneInfo("America/Los_Angeles")


def pacific_now() -> datetime:
    return datetime.now(PACIFIC_TZ)
