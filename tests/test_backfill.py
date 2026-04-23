import pytest
import discord
from datetime import datetime, timezone
import pytz
import asyncio

import main
from main import backfill, event_tracker
from tests.utils_discord_mocks import DummyCtx, DummyAuthor, FakeMessage

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
        FakeReaction("<:share_50:5678>", [user2])
    ]
    
    target_message = FakeBackfillMessage(987654321, "Test Backfill Event", target_author, created_at, reactions)
    
    ctx = DummyCtx()
    ctx.channel = type("Channel", (), {
        "id": 888,
        "fetch_message": lambda mid: asyncio.ensure_future(asyncio.sleep(0)).add_done_callback(lambda x: target_message) or target_message
    })()
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
    
    # Verify attendance
    assert len(event['attendance']) == 2
    assert event['attendance'][101][0] == "User1"
    assert "<:share_100:1234>" in event['attendance'][101][1]
    assert event['attendance'][102][0] == "User2"
    assert "<:share_50:5678>" in event['attendance'][102][1]
    
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
