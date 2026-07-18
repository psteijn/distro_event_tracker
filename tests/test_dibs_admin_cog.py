from types import SimpleNamespace

import pytest

from distro_event_tracker.bot import DibsTracker
from distro_event_tracker.dibs.cog import DibsCog


class FakeResponse:
    def __init__(self):
        self.messages = []
        self.edits = []

    async def send_message(self, content, ephemeral=False, view=None):
        self.messages.append({"content": content, "ephemeral": ephemeral, "view": view})

    async def edit_message(self, *, content, view=None):
        self.edits.append({"content": content, "view": view})


class FakeChannel:
    def __init__(self, channel_id=123):
        self.id = channel_id
        self.messages = []

    async def send(self, content):
        self.messages.append(content)


class FakeContext:
    def __init__(self, user_id=1, channel_id=123):
        self.author = SimpleNamespace(id=user_id, name="Admin", mention="@Admin")
        self.channel = FakeChannel(channel_id)
        self.guild = object()
        self.sent = []

    async def send(self, content=None, *, embed=None, view=None):
        self.sent.append({"content": content, "embed": embed, "view": view})


class FakeInteraction:
    def __init__(self, user_id=1):
        self.user = SimpleNamespace(id=user_id, name="Admin", mention="@Admin")
        self.guild = object()
        self.channel = FakeChannel()
        self.response = FakeResponse()


class FakeRuntime:
    ADMIN_IDS = [1]
    DIBS_CHANNEL_ID = "123"

    def __init__(self):
        self.dibs_tracker = DibsTracker(items_csv="missing-items.csv")
        self.refreshes = []

    async def refresh_dibs_summary(self, guild, **kwargs):
        self.refreshes.append((guild, kwargs))


def test_admin_undibs_help_explains_exact_custom_dibs_item_syntax():
    help_text = DibsCog.admin_undibs.help

    assert "without a `Custom:` prefix" in help_text
    assert "fully match" in help_text
    assert "multi-word names" in help_text.casefold()


@pytest.mark.asyncio
async def test_admin_undibs_removes_multiword_custom_claim_and_refreshes_summary():
    runtime = FakeRuntime()
    runtime.dibs_tracker.add_custom_dib(22, "joke request", 2)
    cog = DibsCog(runtime)
    member = SimpleNamespace(id=22, mention="@Member")
    ctx = FakeContext()

    await cog.admin_undibs.callback(cog, ctx, member, item="joke request")

    assert 22 not in runtime.dibs_tracker.dibs
    assert "Removed @Member's dibs" in ctx.sent[0]["content"]
    assert runtime.refreshes[0][1]["reason"] == "admin_undibs_command"


@pytest.mark.asyncio
async def test_admin_undibs_can_clear_all_claims_for_a_member():
    runtime = FakeRuntime()
    runtime.dibs_tracker.add_dib(22, "Void Aspect Core", 2)
    runtime.dibs_tracker.add_dib(22, "Air Aspect Core", 1)
    cog = DibsCog(runtime)
    ctx = FakeContext()

    await cog.admin_undibs.callback(cog, ctx, SimpleNamespace(id=22, mention="@Member"), item="all")

    assert runtime.dibs_tracker.dibs == {}
    assert "Cleared 2 dibs" in ctx.sent[0]["content"]


@pytest.mark.asyncio
async def test_admin_prefix_controls_reject_non_admin_and_wrong_channel_without_changes():
    runtime = FakeRuntime()
    runtime.dibs_tracker.add_dib(22, "Void Aspect Core", 2)
    cog = DibsCog(runtime)
    member = SimpleNamespace(id=22, mention="@Member")

    non_admin = FakeContext(user_id=9)
    await cog.admin_undibs.callback(cog, non_admin, member, item="all")
    wrong_channel = FakeContext(channel_id=999)
    await cog.admin_undibs.callback(cog, wrong_channel, member, item="all")

    assert 22 in runtime.dibs_tracker.dibs
    assert "permission" in non_admin.sent[0]["content"]
    assert "designated dibs channel" in wrong_channel.sent[0]["content"]
    assert runtime.refreshes == []


@pytest.mark.asyncio
async def test_reset_prefix_command_sends_public_confirmation_and_confirming_resets():
    runtime = FakeRuntime()
    runtime.dibs_tracker.add_dib(22, "Void Aspect Core", 2)
    cog = DibsCog(runtime)
    ctx = FakeContext()

    await cog.reset_dibs.callback(cog, ctx)
    view = ctx.sent[0]["view"]
    interaction = FakeInteraction()
    await view.confirm_reset.callback(interaction)

    assert ctx.sent[0]["content"] == "⚠️ This clears every dibs claim. Confirm to continue."
    assert runtime.dibs_tracker.dibs == {}
    assert "Reset complete" in interaction.response.edits[0]["content"]
    assert runtime.refreshes[0][1]["reason"] == "reset_dibs_command"
    assert interaction.channel.messages == ["⚠️ Dibs have been reset by @Admin."]


@pytest.mark.asyncio
async def test_reset_confirmation_only_accepts_the_invoking_admin_and_cancel_keeps_state():
    runtime = FakeRuntime()
    runtime.dibs_tracker.add_dib(22, "Void Aspect Core", 2)
    cog = DibsCog(runtime)
    ctx = FakeContext()

    await cog.reset_dibs.callback(cog, ctx)
    view = ctx.sent[0]["view"]
    other = FakeInteraction(user_id=9)
    assert await view.interaction_check(other) is False
    await view.cancel_reset.callback(FakeInteraction())

    assert 22 in runtime.dibs_tracker.dibs
    assert "Only the admin" in other.response.messages[0]["content"]
