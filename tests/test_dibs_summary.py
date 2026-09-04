import asyncio

import discord
import pytest

from distro_event_tracker import bot as main
from distro_event_tracker.dibs.summary import DIBS_SUMMARY_PAGE_LENGTH, DIBS_SUMMARY_TITLE


class SummaryChannel:
    id = 123

    def __init__(self):
        self.sent_embeds = []

    async def history(self, limit):
        if False:
            yield limit

    async def send(self, *, embed):
        self.sent_embeds.append(embed)


async def refresh_summary(monkeypatch, dibs):
    channel = SummaryChannel()
    monkeypatch.setattr(main, "DIBS_CHANNEL_ID", "123")
    monkeypatch.setattr(main.dibs_tracker, "dibs", dibs)
    monkeypatch.setattr(main.bot, "get_channel", lambda channel_id: channel)

    await main.refresh_dibs_summary(None)

    return channel.sent_embeds[-1].description


@pytest.mark.asyncio
async def test_dibs_summary_groups_custom_dibs_after_standard_dibs(monkeypatch):
    description = await refresh_summary(
        monkeypatch,
        {
            100: {
                "__custom__:Zulu note": 1,
                "Void Aspect Core": 2,
            },
            200: {
                "__custom__:Alpha note": "Any",
                "Air Aspect Core": "Any",
            },
        },
    )

    assert description == (
        "**Air Aspect Core** | <@200> (Any)\n"
        "**Void Aspect Core** | <@100> (2)\n"
        "\n"
        "**Custom Dibs**\n"
        "**Alpha note** | <@200> (Any)\n"
        "**Zulu note** | <@100> (1)"
    )
    assert "Custom: " not in description


@pytest.mark.asyncio
async def test_dibs_summary_omits_custom_header_without_custom_dibs(monkeypatch):
    description = await refresh_summary(
        monkeypatch,
        {100: {"Void Aspect Core": 2}, 200: {"Air Aspect Core": "Any"}},
    )

    assert description == "**Air Aspect Core** | <@200> (Any)\n**Void Aspect Core** | <@100> (2)"
    assert "Custom Dibs" not in description


@pytest.mark.asyncio
async def test_refresh_sends_large_summary_as_bounded_pages(monkeypatch):
    channel = SummaryChannel()
    dibs = {10**17 + user: {} for user in range(18)}
    for index in range(83):
        dibs[10**17 + (index % 18)][f"Item {index:03d} with a descriptive name"] = 1
    monkeypatch.setattr(main, "DIBS_CHANNEL_ID", "123")
    monkeypatch.setattr(main.dibs_tracker, "dibs", dibs)
    monkeypatch.setattr(main.bot, "get_channel", lambda channel_id: channel)

    await main.refresh_dibs_summary(None)

    summaries = [embed for embed in channel.sent_embeds if embed.title == DIBS_SUMMARY_TITLE]
    assert len(summaries) > 1
    assert all(len(embed.description) <= DIBS_SUMMARY_PAGE_LENGTH for embed in summaries)
    assert [embed.footer.text for embed in summaries] == [
        f"Page {index} of {len(summaries)}" for index in range(1, len(summaries) + 1)
    ]


class StoredMessage:
    def __init__(self, channel, embed, *, label):
        self.channel = channel
        self.author = main.bot.user
        self.embeds = [embed]
        self.label = label
        self.deleted = False

    async def delete(self):
        self.deleted = True
        self.channel.events.append(f"delete:{self.label}")


class ReplacementChannel:
    id = 123

    def __init__(self, *, fail_on_summary=False, history_delay=0):
        self.fail_on_summary = fail_on_summary
        self.history_delay = history_delay
        self.events = []
        self.old_messages = []
        self.replacements = []
        self.active_histories = 0
        self.max_active_histories = 0

    async def history(self, limit):
        self.active_histories += 1
        self.max_active_histories = max(self.max_active_histories, self.active_histories)
        if self.history_delay:
            await asyncio.sleep(self.history_delay)
        for message in self.old_messages:
            yield message
        self.active_histories -= 1

    async def send(self, *, embed):
        self.events.append(f"send:{embed.title}")
        if self.fail_on_summary and embed.title == DIBS_SUMMARY_TITLE:
            raise RuntimeError("simulated Discord failure")
        message = StoredMessage(self, embed, label="replacement")
        self.replacements.append(message)
        return message


def old_summary(channel):
    return StoredMessage(
        channel,
        discord.Embed(title=DIBS_SUMMARY_TITLE, description="old summary"),
        label="old",
    )


@pytest.mark.asyncio
async def test_refresh_keeps_old_summary_when_replacement_send_fails(monkeypatch):
    channel = ReplacementChannel(fail_on_summary=True)
    previous = old_summary(channel)
    channel.old_messages.append(previous)
    monkeypatch.setattr(main, "DIBS_CHANNEL_ID", "123")
    monkeypatch.setattr(main.dibs_tracker, "dibs", {100: {"Void Aspect Core": 1}})
    monkeypatch.setattr(main.bot, "get_channel", lambda channel_id: channel)
    monkeypatch.setattr(main, "_dibs_refresh_lock", asyncio.Lock())

    with pytest.raises(RuntimeError, match="simulated Discord failure"):
        await main.refresh_dibs_summary(None)

    assert previous.deleted is False
    assert channel.replacements
    assert all(message.deleted for message in channel.replacements)


@pytest.mark.asyncio
async def test_refresh_deletes_old_messages_only_after_replacement_is_complete(monkeypatch):
    channel = ReplacementChannel()
    previous = old_summary(channel)
    channel.old_messages.append(previous)
    monkeypatch.setattr(main, "DIBS_CHANNEL_ID", "123")
    monkeypatch.setattr(main.dibs_tracker, "dibs", {100: {"Void Aspect Core": 1}})
    monkeypatch.setattr(main.bot, "get_channel", lambda channel_id: channel)
    monkeypatch.setattr(main, "_dibs_refresh_lock", asyncio.Lock())

    await main.refresh_dibs_summary(None)

    assert previous.deleted is True
    assert channel.events[-1] == "delete:old"


@pytest.mark.asyncio
async def test_concurrent_refreshes_are_serialized(monkeypatch):
    channel = ReplacementChannel(history_delay=0.01)
    monkeypatch.setattr(main, "DIBS_CHANNEL_ID", "123")
    monkeypatch.setattr(main.dibs_tracker, "dibs", {100: {"Void Aspect Core": 1}})
    monkeypatch.setattr(main.bot, "get_channel", lambda channel_id: channel)
    monkeypatch.setattr(main, "_dibs_refresh_lock", asyncio.Lock())

    await asyncio.gather(
        main.refresh_dibs_summary(None, reason="first"),
        main.refresh_dibs_summary(None, reason="second"),
    )

    assert channel.max_active_histories == 1
