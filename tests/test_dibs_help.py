import pytest
from tests.utils_discord_mocks import DummyCtx

from distro_event_tracker.bot import DibsTracker
from distro_event_tracker.dibs.cog import DibsCog


class FakeRuntime:
    def __init__(self):
        self.dibs_tracker = DibsTracker(items_csv="missing-items.csv")


@pytest.mark.asyncio
async def test_help_dibs_documents_admin_controls():
    ctx = DummyCtx()
    cog = DibsCog(FakeRuntime())

    await cog.help_dibs.callback(cog, ctx)

    embed = ctx.sent[0]["embed"]
    values = "\n".join(field.value for field in embed.fields)
    assert "!admin_undibs @member item" in values
    assert "!admin_undibs @member all" in values
    assert "!admin_undibs @member your request" in values
    assert "!reset_dibs" in values
    assert "ADMIN_IDS only" in embed.fields[1].name
