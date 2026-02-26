"""
Tests that creating an event adds all four participation emoji reactions
(25%%, 50%%, 75%%, 100%%), not just one. Regression test for commit 9c6e298.
"""
import pytest
import discord
from datetime import datetime

import main
from main import create_event_with_multiplier, event_tracker
from tests.utils_discord_mocks import DummyCtx, FakeMessage
from config import (
    EVENT_CHANNEL_ID,
    EMOJI_TWENTY_FIVE,
    EMOJI_FIFTY,
    EMOJI_SEVENTY_FIVE,
    EMOJI_HUNDRED,
)
import pytz

PACIFIC_TZ = pytz.timezone("US/Pacific")


@pytest.mark.asyncio
async def test_create_event_adds_all_four_emoji_reactions(monkeypatch):
    """
    When an event is created, the event message must have all four
    participation reactions added (25%%, 50%%, 75%%, 100%%) so users
    can choose their attendance level. Regression: a prior change
    accidentally removed three of the four add_reaction calls.
    """
    event_tracker.events.clear()

    # So we don't need a real channel id match
    monkeypatch.setattr(main, "EVENT_CHANNEL_ID", None)

    # Use string names so we can assert exact emoji identity (no guild needed)
    monkeypatch.setattr(main, "twenty_five_emoji", EMOJI_TWENTY_FIVE)
    monkeypatch.setattr(main, "fifty_emoji", EMOJI_FIFTY)
    monkeypatch.setattr(main, "seventy_five_emoji", EMOJI_SEVENTY_FIVE)
    monkeypatch.setattr(main, "hundred_emoji", EMOJI_HUNDRED)

    ctx = DummyCtx()
    ctx.channel = type("Channel", (), {"id": 999})()
    ctx.message = type("Message", (), {"id": 11111, "created_at": datetime.now(PACIFIC_TZ)})()

    event_message = FakeMessage(message_id=99999, embeds=[])
    event_message.added_reactions = []

    async def record_add_reaction(self, emoji):
        if not hasattr(self, "added_reactions"):
            self.added_reactions = []
        self.added_reactions.append(emoji)

    monkeypatch.setattr(FakeMessage, "add_reaction", record_add_reaction, raising=False)

    async def fake_send(self, msg=None, embed=None):
        self.sent.append({"msg": msg, "embed": embed})
        return event_message

    monkeypatch.setattr(DummyCtx, "send", fake_send, raising=False)

    await create_event_with_multiplier(ctx, "Test Dungeon", 1.0, "🏰", discord.Color.blue())

    assert len(event_message.added_reactions) == 4, (
        "Expected 4 emoji reactions (25%%, 50%%, 75%%, 100%%) on the event message; "
        "got %r" % event_message.added_reactions
    )
    assert event_message.added_reactions == [
        EMOJI_TWENTY_FIVE,
        EMOJI_FIFTY,
        EMOJI_SEVENTY_FIVE,
        EMOJI_HUNDRED,
    ], "Reactions should be in order: 25%%, 50%%, 75%%, 100%%"
