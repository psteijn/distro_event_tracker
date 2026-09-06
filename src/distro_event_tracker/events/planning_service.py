"""State service for event-planning polls."""

from .planning import EventPlan


class PlanningService:
    def __init__(self) -> None:
        self.plans: dict[int, EventPlan] = {}

    def add(self, plan: EventPlan) -> None:
        self.plans[plan.message_id] = plan

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
