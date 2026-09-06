"""State service for event-planning polls."""

from .planning import EventPlan


class PlanningService:
    def __init__(self) -> None:
        self.plans: dict[int, EventPlan] = {}

    def add(self, plan: EventPlan) -> None:
        self.plans[plan.message_id] = plan

    def find_open(
        self, *, plan_id: str | None = None, leader_id: int | None = None
    ) -> EventPlan | None:
        """Find an open plan by visible ID, or the newest one owned by a leader."""
        if plan_id is not None:
            wanted = plan_id.strip().casefold()
            return next(
                (plan for plan in self.plans.values() if plan.id.casefold() == wanted), None
            )
        open_plans = [plan for plan in self.plans.values() if plan.is_open]
        owned = [plan for plan in open_plans if plan.leader_id == leader_id]
        return max(owned, key=lambda plan: plan.message_id, default=None)

    def update_reaction(self, message_id: int, user_id: int, block_index: int, added: bool) -> bool:
        plan = self.plans.get(message_id)
        if plan is None or not plan.is_open:
            return False
        selected = plan.availability.setdefault(user_id, set())
        if added:
            selected.add(block_index)
        else:
            selected.discard(block_index)
            if not selected:
                del plan.availability[user_id]
        return True
