import asyncio
from datetime import datetime, timezone

import pytest
import pytz
from tests.utils_discord_mocks import DummyAuthor, DummyCtx, FakeMessage

from distro_event_tracker import bot as main
from distro_event_tracker.bot import backfill, event_tracker

PACIFIC_TZ = pytz.timezone("US/Pacific")


class AsyncIterator:
    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index < len(self.items):
            item = self.items[self.index]
            self.index += 1
            return item
        else:
            raise StopAsyncIteration


class FakeReaction:
    def __init__(self, emoji, users):
        self.emoji = emoji
        self._users = users

    def users(self):
        return AsyncIterator(self._users)


class FakeBackfillMessage:
    def __init__(self, message_id, content, author, created_at, reactions):
        self.id = message_id
        self.content = content
        self.author = author
        self.created_at = created_at
        self.reactions = reactions
        self.added_reactions = []

    async def add_reaction(self, emoji):
        self.added_reactions.append(emoji)


@pytest.mark.asyncio
async def test_backfill_creates_event_from_message(monkeypatch):
    event_tracker.events.clear()

    # Setup global emojis
    monkeypatch.setattr(main, "hundred_emoji", "💯")
    monkeypatch.setattr(main, "seventy_five_emoji", "75")
    monkeypatch.setattr(main, "fifty_emoji", "50")
    monkeypatch.setattr(main, "twenty_five_emoji", "25")

    # Setup participation emojis
    monkeypatch.setattr(main, "EMOJI_HUNDRED", "share_100")
    monkeypatch.setattr(main, "EMOJI_SEVENTY_FIVE", "share_75")
    monkeypatch.setattr(main, "EMOJI_FIFTY", "share_50")
    monkeypatch.setattr(main, "EMOJI_TWENTY_FIVE", "share_25")

    target_author = DummyAuthor("OriginalCreator", 123)
    created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Reactions
    user1 = DummyAuthor("User1", 101)
    user2 = DummyAuthor("User2", 102)
    # Mock bot user
    bot_user = type("BotUser", (), {"id": 999, "bot": True, "name": "Bot"})()
    user1.bot = False
    user2.bot = False

    reactions = [
        FakeReaction("<:share_100:1234>", [user1, bot_user]),
        FakeReaction("<:share_50:5678>", [user2]),
    ]

    target_message = FakeBackfillMessage(
        987654321, "Test Backfill Event", target_author, created_at, reactions
    )

    ctx = DummyCtx()

    # Mock send to return a message with an id
    async def fake_send(*args, **kwargs):
        msg = FakeMessage()
        msg.id = 555
        # Also record it in ctx.sent for the other test
        ctx.sent.append(
            {"msg": args[0] if args else kwargs.get("content"), "embed": kwargs.get("embed")}
        )
        return msg

    ctx.send = fake_send

    ctx.channel = type(
        "Channel",
        (),
        {
            "id": 888,
            "fetch_message": lambda mid: asyncio.ensure_future(asyncio.sleep(0)).add_done_callback(
                lambda x: target_message
            )
            or target_message,
        },
    )()

    # async fetch_message mock
    async def fake_fetch_message(mid):
        return target_message

    ctx.channel.fetch_message = fake_fetch_message

    ctx.message = type("Message", (), {"id": 111, "created_at": datetime.now(timezone.utc)})()

    await backfill(ctx, "boss", 987654321)

    # Verify event was created
    assert len(event_tracker.events) == 1
    event_id = list(event_tracker.events.keys())[0]
    event = event_tracker.events[event_id]

    assert event['name'] == "Test Backfill Event"
    assert event['multiplier'] == 2.0
    assert event['type_emoji'] == "👹"

    # Verify attendance (now imported as manual_attendance)
    assert len(event['manual_attendance']) == 2

    user1_entry = next(u for u in event['manual_attendance'] if u['name'] == "User1")
    assert user1_entry['multiplier'] == 1.0

    user2_entry = next(u for u in event['manual_attendance'] if u['name'] == "User2")
    assert user2_entry['multiplier'] == 0.5

    # Verify bot reactions added to the new message
    # In the code, event_message is the one that gets reactions
    # We returned target_message from ctx.send in a real scenario, but here ctx.send returns None by default in DummyCtx
    # I should update DummyCtx to return a FakeMessage


@pytest.mark.asyncio
async def test_backfill_invalid_type(ctx=None):
    event_tracker.events.clear()
    ctx = DummyCtx()
    await backfill(ctx, "invalid_type", 123)
    assert "Invalid event type" in ctx.sent[0]['msg']
    assert len(event_tracker.events) == 0
