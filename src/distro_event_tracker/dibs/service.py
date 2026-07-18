"""Pure admin operations for dibs state."""

from dataclasses import dataclass
from typing import Protocol

from .persistence import CUSTOM_DIBS_PREFIX


class DibsState(Protocol):
    """The tracker surface required by the admin dibs operations."""

    dibs: dict[int, dict[str, object]]

    def remove_all_dibs(self, user_id: int) -> bool: ...

    def remove_dib(self, user_id: int, item_name: str) -> bool: ...

    @staticmethod
    def display_dib_item_name(item_name: str) -> str: ...


@dataclass(frozen=True, slots=True)
class AdminDibsResult:
    """The outcome of an administrative dibs operation."""

    changed: bool
    display_item: str | None = None
    removed_claims: int = 0
    removed_members: int = 0


class DibsAdminService:
    """Admin state changes independent of Discord adapters."""

    def __init__(self, tracker: DibsState):
        self.tracker = tracker

    def remove_for_member(self, member_id: int, item: str) -> AdminDibsResult:
        """Remove one member's selected claim, or all of their claims."""
        if item.casefold() == "all":
            claims = len(self.tracker.dibs.get(member_id, {}))
            changed = self.tracker.remove_all_dibs(member_id)
            return AdminDibsResult(changed=changed, removed_claims=claims)

        stored_item = self._resolve_exact_claim(member_id, item)
        if not stored_item:
            return AdminDibsResult(changed=False)

        changed = self.tracker.remove_dib(member_id, stored_item)
        return AdminDibsResult(
            changed=changed,
            display_item=self.tracker.display_dib_item_name(stored_item),
            removed_claims=1 if changed else 0,
        )

    def _resolve_exact_claim(self, member_id: int, item: str) -> str | None:
        """Resolve one standard or custom claim by its full displayed text."""
        query = " ".join(item.split()).casefold()
        if not query:
            return None

        matches = []
        for stored_item in self.tracker.dibs.get(member_id, {}):
            claim_text = (
                stored_item.removeprefix(CUSTOM_DIBS_PREFIX)
                if stored_item.startswith(CUSTOM_DIBS_PREFIX)
                else stored_item
            )
            if " ".join(claim_text.split()).casefold() == query:
                matches.append(stored_item)

        return matches[0] if len(matches) == 1 else None

    def reset(self) -> AdminDibsResult:
        """Clear every member's dibs without changing the item catalog."""
        removed_members = len(self.tracker.dibs)
        removed_claims = sum(len(claims) for claims in self.tracker.dibs.values())
        self.tracker.dibs.clear()
        return AdminDibsResult(
            changed=bool(removed_claims),
            removed_claims=removed_claims,
            removed_members=removed_members,
        )
