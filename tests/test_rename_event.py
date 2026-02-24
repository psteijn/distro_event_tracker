import pytest
import discord

import main
from main import event_tracker, rename_event
from tests.utils_discord_mocks import DummyCtx, FakeMessage, FakeChannel


@pytest.mark.asyncio
async def test_rename_event_happy_case(monkeypatch):
    """
    Event creator renames their own event.
    The in-memory name and the embed title should both update.
    """
    event_tracker.events.clear()

    # Context with an author; DummyCtx.author.id will be used as creator_id
    ctx = DummyCtx()
    creator_id = ctx.author.id

    event_tracker.events["evt1"] = {
        "id": "evt1",
        "name": "Old Name",
        "type_emoji": "🏰",
        "channel_id": 123,
        "message_id": 456,
        "creator_id": creator_id,
        "created_at": 0,
        "multiplier": 1.0,
        "attendance": {},
        "manual_attendance": [],
    }

    # Original event message has an embed with the emoji prefix
    base_embed = discord.Embed(title="🏰 Old Name", description="Dungeon event")
    fake_message = FakeMessage(message_id=456, embeds=[base_embed])
    fake_channel = FakeChannel(fake_message)

    def fake_get_channel(channel_id: int):
        assert channel_id == 123
        return fake_channel

    monkeypatch.setattr(main.bot, "get_channel", fake_get_channel)

    # Act
    await rename_event.callback(ctx, "evt1", new_name="New Name")

    # In-memory event name should be updated
    event = event_tracker.events["evt1"]
    assert event["name"] == "New Name"

    # The event message embed should also be updated
    edited_embed = fake_message.edited_embed
    assert edited_embed is not None
    assert edited_embed.title == "🏰 New Name"

    # A success embed should have been sent
    assert len(ctx.sent) == 1
    sent_embed = ctx.sent[0]["embed"]
    assert sent_embed is not None
    assert sent_embed.title == "✅ Event Renamed"
    # Check fields for old/new name & event ID
    fields = {f.name: f.value for f in sent_embed.fields}
    assert fields.get("Event ID") == "evt1"
    assert fields.get("Old Name") == "Old Name"
    assert fields.get("New Name") == "New Name"
