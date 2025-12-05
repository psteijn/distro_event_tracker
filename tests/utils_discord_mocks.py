class DummyAuthor:
    """Minimal stand-in for ctx.author."""
    def __init__(self, name="TestUser", user_id=1):
        self.name = name
        self.id = user_id


class DummyCtx:
    """Minimal stand-in for a discord.py Context."""
    def __init__(self, author=None):
        self.sent = []
        if author is not None:
            self.author = author
        else:
            self.author = DummyAuthor()

    async def send(self, msg=None, embed=None):
        self.sent.append({"msg": msg, "embed": embed})


class FakeMessage:
    """Fake Discord message object with just enough surface for add_users."""
    def __init__(self, message_id=456, embeds=None):
        self.id = message_id
        self.embeds = embeds or []
        self.edited_embed = None  # capture last edited embed

    async def edit(self, *, embed=None):
        # Simulate Discord's Message.edit(embed=...)
        self.edited_embed = embed
        # also keep embeds list in sync so later reads see it
        if embed is not None:
            self.embeds = [embed]


class FakeChannel:
    """Fake channel that returns a preconfigured message."""
    def __init__(self, message):
        self._message = message

    async def fetch_message(self, message_id):
        # Ignore message_id for this simple test; always return the fake message
        return self._message


class FakeMember:
    """Minimal stand-in for a discord.Member."""
    def __init__(self, name):
        self.name = name
        # mention is not strictly needed for add_users, but handy if used later
        self.mention = f"@{name}"
