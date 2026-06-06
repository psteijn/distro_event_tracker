import pytest

from distro_event_tracker import bot as runtime
from distro_event_tracker.bootstrap import install_cogs


@pytest.mark.asyncio
async def test_install_cogs_registers_feature_commands(monkeypatch):
    monkeypatch.setattr(runtime, "DIBS_CHANNEL_ID", "123")
    test_bot = runtime.EventBot(command_prefix="!", intents=runtime.intents)

    await install_cogs(test_bot, runtime, runtime.DIBS_CHANNEL_ID)

    assert set(test_bot.cogs) == {"Events", "Dibs"}
    assert test_bot.get_command("summary").cog_name == "Events"
    assert test_bot.get_command("dibs_data").cog_name == "Dibs"
    assert {command.name for command in test_bot.commands} == {
        "add_users",
        "backfill",
        "boss",
        "data",
        "delete_event",
        "dibs_data",
        "dungeon",
        "help",
        "help_events",
        "miniboss",
        "missing",
        "omniboss",
        "reminders",
        "rename",
        "summary",
        "t8",
    }
    assert {command.name for command in test_bot.tree.get_commands()} == {
        "custom_dibs",
        "dibs",
        "undibs",
    }
    await test_bot.close()


@pytest.mark.asyncio
async def test_install_cogs_hides_slash_dibs_without_channel(monkeypatch):
    monkeypatch.setattr(runtime, "DIBS_CHANNEL_ID", "")
    test_bot = runtime.EventBot(command_prefix="!", intents=runtime.intents)

    await install_cogs(test_bot, runtime, runtime.DIBS_CHANNEL_ID)

    assert test_bot.get_command("dibs_data").cog_name == "Dibs"
    assert test_bot.tree.get_commands() == []
    await test_bot.close()
