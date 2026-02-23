import pytest
import main
from main import event_tracker, delete_event
from tests.utils_discord_mocks import DummyCtx, FakeMessage, FakeChannel


@pytest.mark.asyncio
async def test_delete_event_happy_case(monkeypatch):
    """
    Creator confirms deletion (✅).
    The event is removed from memory and a success embed is sent.
    """
    event_tracker.events.clear()

    ctx = DummyCtx()
    creator_id = ctx.author.id

    # Event to be deleted
    event_tracker.events["evt1"] = {
        "id": "evt1",
        "name": "Delete Me",
        "channel_id": 123,
        "message_id": 456,
        "creator_id": creator_id,
        "created_at": 0,
        "multiplier": 1.0,
        "attendance": {},
        "manual_attendance": [],
    }

    # This is the original event message that will be deleted
    event_message = FakeMessage(message_id=456, embeds=[])

    fake_channel = FakeChannel(event_message)

    def fake_get_channel(channel_id: int):
        assert channel_id == 123
        return fake_channel

    monkeypatch.setattr(main.bot, "get_channel", fake_get_channel)

    # Patch FakeMessage.delete & add_reaction so they don't explode
    async def fake_delete(self):
        self.deleted = True

    async def fake_add_reaction(self, emoji):
        if not hasattr(self, "added_reactions"):
            self.added_reactions = []
        self.added_reactions.append(emoji)

    monkeypatch.setattr(FakeMessage, "delete", fake_delete, raising=False)
    monkeypatch.setattr(FakeMessage, "add_reaction", fake_add_reaction, raising=False)

    # When ctx.send(embed=...) is called for the confirmation message,
    # we want to return a FakeMessage so delete_event can attach reactions to it.
    confirmation_holder = {}

    async def fake_ctx_send(self, msg=None, embed=None):
        # Record what was sent
        self.sent.append({"msg": msg, "embed": embed})
        if embed is not None:
            m = FakeMessage(message_id=999, embeds=[embed])
            confirmation_holder["message"] = m
            return m
        return None

    monkeypatch.setattr(DummyCtx, "send", fake_ctx_send, raising=False)

    # Fake reaction object for wait_for
    class FakeReaction:
        def __init__(self, emoji, message):
            self.emoji = emoji
            self.message = message

    async def fake_wait_for(event_name, timeout=None, check=None):
        # Simulate the user clicking ✅ on the confirmation message
        msg = confirmation_holder["message"]
        reaction = FakeReaction("✅", msg)
        user = ctx.author
        assert check(reaction, user)
        return reaction, user

    monkeypatch.setattr(main.bot, "wait_for", fake_wait_for)

    # Act
    await delete_event.callback(ctx, "evt1")

    # Event should be gone
    assert "evt1" not in event_tracker.events

    # Original event message should have been "deleted"
    assert getattr(event_message, "deleted", False) is True

    # The last thing sent should be a success embed
    # We expect two sends: confirmation embed, then success embed
    assert len(ctx.sent) >= 2
    success_embed = ctx.sent[-1]["embed"]
    assert success_embed is not None
    assert success_embed.title == "✅ Event Deleted"
    fields = {f.name: f.value for f in success_embed.fields}
    assert fields.get("Event ID") == "evt1"
