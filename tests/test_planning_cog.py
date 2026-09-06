from types import SimpleNamespace

from distro_event_tracker.events.planning_cog import PlanningCog
from test_planning import make_plan


def test_public_planning_card_uses_localized_timestamps_for_every_time_range():
    plan = make_plan()
    cog = PlanningCog(SimpleNamespace(), "2")

    embed = cog._embed(plan)
    values = [field.value for field in embed.fields if field.name.startswith("Availability ·")]

    assert "All times below are shown in your local timezone." in embed.description
    assert (
        next(field.value for field in embed.fields if field.name == "Availability window").count(
            "<t:"
        )
        == 2
    )
    assert sum(value.count("<t:") for value in values) == 8
