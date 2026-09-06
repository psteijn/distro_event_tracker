from datetime import datetime, timezone

import discord
import pytest

from distro_event_tracker.events.planning_draft import PlanningDraft
from distro_event_tracker.events.planning_wizard import PlanningWizard


@pytest.mark.asyncio
async def test_wizard_defaults_to_afternoon_choices_in_the_organizers_timezone():
    now = datetime(2026, 9, 12, 15, 0, tzinfo=timezone.utc)
    draft = PlanningDraft(leader_id=1, channel_id=2, name="Bosses")
    wizard = PlanningWizard(None, draft, now=lambda: now)

    wizard.advance("continue", "")
    wizard.advance("day", "2026-09-13")
    wizard.render()
    beginning = next(item for item in wizard.children if isinstance(item, discord.ui.Select))

    assert beginning.placeholder == "Choose beginning"
    assert beginning.options
    assert all(option.label.endswith("PM") for option in beginning.options)
    wizard.stop()
