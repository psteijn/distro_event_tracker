import logging

import pytest

from distro_event_tracker import bot as runtime


class SyncCommand:
    def __init__(self, name):
        self.name = name


@pytest.mark.asyncio
async def test_command_sync_logs_and_marks_tree_ready(monkeypatch, caplog):
    bot = runtime.EventBot(command_prefix="!", intents=runtime.intents)
    caplog.set_level(logging.INFO, logger="bot")
    planned = [SyncCommand("plan"), SyncCommand("event")]
    returned = [SyncCommand("event"), SyncCommand("plan")]
    monkeypatch.setattr(bot.tree, "get_commands", lambda: planned)

    async def sync():
        return returned

    monkeypatch.setattr(bot.tree, "sync", sync)

    assert await bot.sync_application_commands()
    assert bot.command_tree_synced
    assert "APPLICATION_COMMAND_SYNC planned_commands=['event', 'plan']" in caplog.text
    assert "APPLICATION_COMMAND_SYNC succeeded" in caplog.text
