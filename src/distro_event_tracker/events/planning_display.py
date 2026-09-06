"""Discord timestamp and embed-field formatting for planning."""

from datetime import datetime

from .planning import PlanBlock, availability_periods

LOCAL_TIME_NOTE = "All times below are shown in your local timezone."


def timestamp(value: datetime) -> str:
    return f"<t:{int(value.timestamp())}:f>"


def time_range(start: datetime, end: datetime) -> str:
    return f"{timestamp(start)} – {timestamp(end)}"


def local_availability(indices: set[int], blocks: list[PlanBlock]) -> str:
    return ", ".join(time_range(start, end) for start, end in availability_periods(indices, blocks))


def field_pages(rows: list[str], limit: int = 1024) -> list[str]:
    pages: list[str] = []
    page = ""
    for row in rows:
        if len(row) > limit:
            raise ValueError("An availability row exceeds the Discord field limit.")
        if page and len(page) + 1 + len(row) > limit:
            pages.append(page)
            page = ""
        page = f"{page}\n{row}" if page else row
    if page:
        pages.append(page)
    return pages
