from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from distro_event_tracker.events.planning import build_blocks
from distro_event_tracker.events.planning_cog import PlanningCog
from distro_event_tracker.events.planning_service import PlanningService
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


def test_scheduled_notification_card_is_self_contained_and_personalized():
    plan = make_plan()
    blocks = build_blocks(plan.starts_at, plan.ends_at)
    plan.scheduled_start, plan.scheduled_end = blocks[1].start, blocks[2].end
    plan.details = "Meet in voice five minutes early."
    cog = PlanningCog(SimpleNamespace(), "2")

    embed = cog._scheduled_notification_embed(
        plan,
        selected={1},
        blocks=blocks,
        start_index=1,
        end_index=3,
        guild_name="Distro",
        jump_url="https://discord.com/channels/1/2/3",
    )

    assert embed.title == "Bosses is happening!"
    assert embed.description == "Distro · Led by <@3>"
    assert embed.footer.text == "All times below are shown in your local timezone."
    assert [(field.name, field.value) for field in embed.fields] == [
        ("When", "<t:1789237800:f> – <t:1789241400:f>"),
        (
            "Your availability",
            "You marked yourself available for part of the event:\n"
            "<t:1789237800:f> – <t:1789239600:f>",
        ),
        ("Details", "Meet in voice five minutes early."),
        ("Event plan", "[View event plan](https://discord.com/channels/1/2/3)"),
    ]


def test_custom_emojis_use_ice_number_names():
    ice_one = SimpleNamespace(name="ice_1")
    ice_two = SimpleNamespace(name="ice_2")

    assert PlanningCog._custom_emojis(SimpleNamespace(emojis=[ice_two, ice_one]), 2) == [
        ice_one,
        ice_two,
    ]


def test_custom_emojis_report_missing_ice_number_names():
    with pytest.raises(ValueError, match=r"custom emojis named :ice_1:, :ice_2:"):
        PlanningCog._custom_emojis(SimpleNamespace(emojis=[]), 2)


@pytest.mark.parametrize(
    ("emoji", "expected"),
    [
        (SimpleNamespace(name="ice_1"), 0),
        (SimpleNamespace(name="ice_20"), 19),
        (SimpleNamespace(name="1"), 0),
        (SimpleNamespace(name="20"), 19),
        (SimpleNamespace(name="ice_21"), None),
    ],
)
def test_reaction_index_accepts_ice_emojis_and_legacy_numeric_emojis(emoji, expected):
    assert PlanningCog._reaction_index(emoji) == expected


@pytest.mark.asyncio
async def test_post_draft_uses_interaction_permissions_when_creator_is_not_cached(monkeypatch):
    permissions = SimpleNamespace(
        view_channel=True,
        use_application_commands=True,
        send_messages=True,
        embed_links=True,
        add_reactions=True,
        read_message_history=True,
    )
    posted_message = SimpleNamespace(id=4, jump_url="https://discord.com/channels/1/2/4")
    posted_message.add_reaction = AsyncMock()
    channel = SimpleNamespace(
        permissions_for=MagicMock(return_value=permissions),
        send=AsyncMock(return_value=posted_message),
    )
    guild = SimpleNamespace(
        me=SimpleNamespace(id=99),
        get_member=MagicMock(return_value=None),
        emojis=[],
    )
    interaction = SimpleNamespace(
        channel_id=2,
        channel=channel,
        guild=guild,
        permissions=permissions,
        edit_original_response=AsyncMock(),
    )
    draft = SimpleNamespace(
        leader_id=1,
        channel_id=2,
        validate_details=MagicMock(),
        validate_times=MagicMock(),
        to_plan=MagicMock(return_value=make_plan()),
    )
    cog = PlanningCog(SimpleNamespace(user=SimpleNamespace(id=99)), "2")
    monkeypatch.setattr(cog, "_custom_emojis", lambda guild, count: [])

    await cog.post_draft(interaction, draft)

    channel.send.assert_awaited_once()
    interaction.edit_original_response.assert_awaited_once_with(
        content="Poll posted: https://discord.com/channels/1/2/4", embed=None, view=None
    )


@pytest.mark.asyncio
async def test_schedule_sends_personalized_cards_and_continues_after_a_failed_dm():
    plan = make_plan()
    plan.availability = {10: {0, 1}, 11: {1}, 12: {3}}
    service = PlanningService()
    service.add(plan)

    message = SimpleNamespace(jump_url="https://discord.com/channels/1/2/3", edit=AsyncMock())
    channel = SimpleNamespace(fetch_message=AsyncMock(return_value=message))
    unavailable_response = SimpleNamespace(status=403, reason="Forbidden", headers={})
    unavailable_user = SimpleNamespace(
        send=AsyncMock(side_effect=discord.Forbidden(unavailable_response, "DMs are closed"))
    )
    available_user = SimpleNamespace(send=AsyncMock())
    bot = SimpleNamespace(
        get_channel=MagicMock(return_value=channel),
        get_user=MagicMock(
            side_effect=lambda user_id: {10: unavailable_user, 11: available_user}[user_id]
        ),
        fetch_user=AsyncMock(),
    )
    interaction = SimpleNamespace(
        channel_id=2,
        user=SimpleNamespace(id=3, guild_permissions=SimpleNamespace(manage_messages=False)),
        guild=SimpleNamespace(name="Distro"),
        response=SimpleNamespace(send_message=AsyncMock()),
    )
    cog = PlanningCog(bot, "2", service)

    await PlanningCog.schedule.callback(cog, interaction, start=1, end=2)

    assert unavailable_user.send.call_count == 1
    available_user.send.call_count == 1
    assert bot.get_user.call_args_list[-1].args == (11,)
    sent_embed = available_user.send.call_args.kwargs["embed"]
    assert sent_embed.title == "Bosses is happening!"
    assert next(
        field.value for field in sent_embed.fields if field.name == "Your availability"
    ) == (
        "You marked yourself available for part of the event:\n"
        "<t:1789237800:f> – <t:1789239600:f>"
    )
    assert available_user.send.call_args.kwargs["allowed_mentions"].everyone is False
