"""Discord timestamp and embed-field formatting for planning."""

from datetime import datetime
from typing import Sequence

from .planning import PlanBlock, availability_periods

LOCAL_TIME_NOTE = "All times below are shown in your local timezone."
DM_TIME_NOTE = "All times are in your local timezone."
ZERO_WIDTH_SPACE = "\u200b"


def timestamp(value: datetime) -> str:
    return f"<t:{int(value.timestamp())}:f>"


def compact_timestamp(value: datetime) -> str:
    """Return Discord's localized short date-and-time representation."""
    return f"<t:{int(value.timestamp())}:s>"


def time_range(start: datetime, end: datetime) -> str:
    return f"{timestamp(start)} – {timestamp(end)}"


def compact_time_range(start: datetime, end: datetime) -> str:
    return f"{compact_timestamp(start)} – {compact_timestamp(end)}"


def availability_legend(minimum: int | None, maximum: int | None) -> str:
    """Explain the compact status symbols shown beside availability slots."""
    notes = ["30-minute slots", "local time"]
    if minimum is not None:
        notes.append("✓ minimum met")
    if maximum is not None:
        notes.append("⚠ above preferred maximum")
    return " · ".join(notes)


def availability_rows(
    blocks: Sequence[PlanBlock],
    counts: Sequence[int],
    *,
    minimum: int | None,
    maximum: int | None,
    slot_labels: Sequence[str] | None = None,
) -> list[str]:
    """Render concise, localized availability rows in chronological order."""
    rows: list[str] = []
    for index, (block, count) in enumerate(zip(blocks, counts), start=1):
        label = slot_labels[index - 1] if slot_labels and index <= len(slot_labels) else str(index)
        marker = ""
        if maximum is not None and count > maximum:
            marker = " ⚠"
        elif minimum is not None and count >= minimum:
            marker = " ✓"
        rows.append(f"{label} {compact_timestamp(block.start)} · {count} available{marker}")
    return rows


def local_availability(indices: set[int], blocks: list[PlanBlock]) -> str:
    return ", ".join(time_range(start, end) for start, end in availability_periods(indices, blocks))


def scheduled_availability_message(
    selected: set[int], blocks: list[PlanBlock], start_index: int, end_index: int
) -> str:
    """Explain whether a member selected all or part of the scheduled event."""
    scheduled = set(range(start_index, end_index))
    if selected == scheduled:
        return "You marked yourself available for the whole event."
    return "You marked yourself available for part of the event:\n" + "\n".join(
        time_range(start, end) for start, end in availability_periods(selected, blocks)
    )


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
