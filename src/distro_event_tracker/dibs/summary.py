"""Pure formatting and pagination for the human-readable dibs summary."""

from collections.abc import Mapping

from .persistence import CUSTOM_DIBS_PREFIX

DIBS_SUMMARY_TITLE = "📦 Current Dibs Summary"
DIBS_SUMMARY_PAGE_LENGTH = 4000


def build_dibs_summary_pages(
    dibs: Mapping[int, Mapping[str, object]],
    *,
    page_length: int = DIBS_SUMMARY_PAGE_LENGTH,
) -> list[str]:
    """Build summary descriptions that fit Discord's embed description limit."""
    if page_length <= 0:
        raise ValueError("page_length must be positive")
    if not dibs:
        return ["No active dibs."]

    item_to_users: dict[str, list[tuple[int, object]]] = {}
    for user_id, user_dibs in dibs.items():
        for item, quantity in user_dibs.items():
            item_to_users.setdefault(item, []).append((user_id, quantity))

    def format_claim_line(item: str, *, custom: bool = False) -> str:
        claims = []
        for user_id, quantity in item_to_users[item]:
            quantity_text = str(quantity) if quantity else "Any"
            claims.append(f"<@{user_id}> ({quantity_text})")

        display_item = item.removeprefix(CUSTOM_DIBS_PREFIX) if custom else item
        return f"**{display_item}** | {', '.join(claims)}"

    standard_items = sorted(
        item for item in item_to_users if not item.startswith(CUSTOM_DIBS_PREFIX)
    )
    custom_items = sorted(item for item in item_to_users if item.startswith(CUSTOM_DIBS_PREFIX))

    lines = [format_claim_line(item) for item in standard_items]
    if custom_items:
        lines.extend(["", "**Custom Dibs**"])
        lines.extend(format_claim_line(item, custom=True) for item in custom_items)

    return _paginate_lines(lines, page_length)


def _paginate_lines(lines: list[str], page_length: int) -> list[str]:
    pages: list[str] = []
    current_lines: list[str] = []
    current_length = 0

    for line in lines:
        for line_part in _split_long_line(line, page_length):
            separator_length = 1 if current_lines else 0
            if current_lines and current_length + separator_length + len(line_part) > page_length:
                pages.append("\n".join(current_lines))
                current_lines = []
                current_length = 0
                separator_length = 0

            current_lines.append(line_part)
            current_length += separator_length + len(line_part)

    if current_lines:
        pages.append("\n".join(current_lines))

    return pages or [""]


def _split_long_line(line: str, page_length: int) -> list[str]:
    """Split even a single pathological claim line without dropping content."""
    if len(line) <= page_length:
        return [line]

    parts = []
    remaining = line
    while len(remaining) > page_length:
        split_at = remaining.rfind(", ", 0, page_length + 1)
        if split_at <= 0:
            split_at = page_length
            parts.append(remaining[:split_at])
            remaining = remaining[split_at:]
        else:
            parts.append(remaining[:split_at])
            remaining = remaining[split_at + 2 :]

    if remaining:
        parts.append(remaining)
    return parts
