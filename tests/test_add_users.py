
import pytest
import discord

import main
from main import event_tracker, add_users, multiplier_to_emoji_string
from tests.utils_discord_mocks import DummyCtx, FakeMessage, FakeChannel, FakeMember
from config import EMOJI_HUNDRED


@pytest.mark.asyncio
async def test_add_users_happy_case(monkeypatch):
    # Arrange: clear events and create a base event
    event_tracker.events.clear()
    event_tracker.events["evt1"] = {
        "id": "evt1",
        "name": "Test Event",
        "type_emoji": "🏰",
        "channel_id": 123,
        "message_id": 456,
        "creator_id": 1,
        "created_at": 0,
        "multiplier": 1.0,
        "attendance": {},
        "manual_attendance": [],
    }

    # Start with a simple embed on the message
    base_embed = discord.Embed(title="🏰 Test Event", description="Test description")
    fake_message = FakeMessage(message_id=456, embeds=[base_embed])
    fake_channel = FakeChannel(fake_message)

    # Monkeypatch bot.get_channel to return our fake channel
    def fake_get_channel(channel_id: int):
        assert channel_id == 123
        return fake_channel

    monkeypatch.setattr(main.bot, "get_channel", fake_get_channel)

    # Context and member to add
    ctx = DummyCtx()
    member = FakeMember("Alice")

    # Act: call the command's underlying callback
    # Signature: (ctx, event_id: str, multiplier: float, *members: discord.Member)
    await add_users.callback(ctx, "evt1", 1.0, member)

    # Assert: manual_attendance updated on the event
    event = event_tracker.events["evt1"]
    assert event["manual_attendance"] == [{"name": "Alice", "multiplier": 1.0}]

    # The command should have sent a confirmation message
    assert len(ctx.sent) == 1
    confirmation = ctx.sent[0]["msg"]
    assert "Successfully added 1 user(s)" in confirmation
    assert "Alice" in confirmation

    # The embed on the message should have been updated with a "Manual Attendance" field
    edited_embed = fake_message.edited_embed
    assert edited_embed is not None

    manual_field = None
    for field in edited_embed.fields:
        if field.name == "Manual Attendance":
            manual_field = field
            break

    assert manual_field is not None, "Expected a 'Manual Attendance' field on the embed"
    assert manual_field.value == f"{EMOJI_HUNDRED} Alice"


@pytest.mark.asyncio
async def test_add_users_invalid_multiplier(monkeypatch):
    """
    If multiplier is not one of (1.0, 0.75, 0.5, 0.25),
    the command should send an error and not touch the event.
    """
    event_tracker.events.clear()
    event_tracker.events["evt1"] = {
        "id": "evt1",
        "name": "Test Event",
        "type_emoji": "🏰",
        "channel_id": 123,
        "message_id": 456,
        "creator_id": 1,
        "created_at": 0,
        "multiplier": 1.0,
        "attendance": {},
        "manual_attendance": [],
    }

    # We don't actually need a real channel here, because we should bail
    # before trying to fetch the message.
    def fake_get_channel(channel_id: int):
        return None

    monkeypatch.setattr(main.bot, "get_channel", fake_get_channel)

    ctx = DummyCtx()
    member = FakeMember("Alice")

    await add_users.callback(ctx, "evt1", 0.33, member)

    # Should send a nice error
    assert len(ctx.sent) == 1
    assert "Multiplier must be exactly 1.0, 0.75, 0.5, or 0.25" in ctx.sent[0]["msg"]

    # Event should remain untouched
    assert event_tracker.events["evt1"]["manual_attendance"] == []


@pytest.mark.asyncio
async def test_add_users_event_not_found(monkeypatch):
    """
    If the event_id does not exist, the command should send an error.
    """
    event_tracker.events.clear()

    def fake_get_channel(channel_id: int):
        return None

    monkeypatch.setattr(main.bot, "get_channel", fake_get_channel)

    ctx = DummyCtx()
    member = FakeMember("Alice")

    await add_users.callback(ctx, "no_such_event", 1.0, member)

    assert len(ctx.sent) == 1
    assert "Event with ID `no_such_event` not found." in ctx.sent[0]["msg"]


@pytest.mark.asyncio
async def test_add_users_no_members(monkeypatch):
    """
    If no members are passed after event_id and multiplier,
    the command should send the 'need at least one user' error.
    """
    event_tracker.events.clear()
    event_tracker.events["evt1"] = {
        "id": "evt1",
        "name": "Test Event",
        "type_emoji": "🏰",
        "channel_id": 123,
        "message_id": 456,
        "creator_id": 1,
        "created_at": 0,
        "multiplier": 1.0,
        "attendance": {},
        "manual_attendance": [],
    }

    def fake_get_channel(channel_id: int):
        return None

    monkeypatch.setattr(main.bot, "get_channel", fake_get_channel)

    ctx = DummyCtx()

    # Note: no member args passed here
    await add_users.callback(ctx, "evt1", 1.0)

    assert len(ctx.sent) == 1
    assert "You need to specify at least one user to add" in ctx.sent[0]["msg"]

    # No manual attendance should be recorded
    assert event_tracker.events["evt1"]["manual_attendance"] == []


@pytest.mark.asyncio
async def test_add_users_overwrites_existing_manual_and_updates_embed(monkeypatch):
    """
    If a user already exists in manual_attendance, add_users should
    remove the old entry and add the new one with the new multiplier,
    and the embed's Manual Attendance field should reflect that.
    """
    event_tracker.events.clear()
    event_tracker.events["evt1"] = {
        "id": "evt1",
        "name": "Test Event",
        "type_emoji": "🏰",
        "channel_id": 123,
        "message_id": 456,
        "creator_id": 1,
        "created_at": 0,
        "multiplier": 1.0,
        "attendance": {},
        "manual_attendance": [
            {"name": "Alice", "multiplier": 0.5},  # existing, will be overwritten
        ],
    }

    base_embed = discord.Embed(title="🏰 Test Event")
    # Existing Manual Attendance field simulating previous state
    base_embed.add_field(name="Manual Attendance", value="old", inline=True)

    fake_message = FakeMessage(message_id=456, embeds=[base_embed])
    fake_channel = FakeChannel(fake_message)

    def fake_get_channel(channel_id: int):
        assert channel_id == 123
        return fake_channel

    monkeypatch.setattr(main.bot, "get_channel", fake_get_channel)

    ctx = DummyCtx()
    member = FakeMember("Alice")

    # Overwrite Alice with multiplier 0.75
    await add_users.callback(ctx, "evt1", 0.75, member)

    # Manual attendance should contain a single entry for Alice with new multiplier
    event = event_tracker.events["evt1"]
    assert event["manual_attendance"] == [
        {"name": "Alice", "multiplier": 0.75}
    ]

    # Should have sent a success message only
    assert len(ctx.sent) == 1
    assert "Successfully added 1 user(s)" in ctx.sent[0]["msg"]

    # Embed updated
    updated_embed = fake_message.edited_embed
    assert updated_embed is not None

    manual_field = next(
        (f for f in updated_embed.fields if f.name == "Manual Attendance"),
        None,
    )
    assert manual_field is not None

    expected_emoji = main.multiplier_to_emoji_string(0.75)
    assert manual_field.value == f"{expected_emoji} Alice"