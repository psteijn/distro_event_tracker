import json
import urllib.parse

import discord
import pytest

from distro_event_tracker import bot as main
from distro_event_tracker.dibs.persistence import DIBS_DATA_TITLE, DIBS_DATA_URL
from distro_event_tracker.dibs.summary import DIBS_SUMMARY_TITLE


class HistoryMessage:
    def __init__(self, author, embed):
        self.author = author
        self.embeds = [embed]


class HistoryChannel:
    def __init__(self, messages):
        self.messages = messages

    async def history(self, limit):
        for message in self.messages:
            yield message


class HistoryBot:
    def __init__(self, messages):
        self.user = object()
        self.messages = messages

    def get_channel(self, channel_id):
        return HistoryChannel([HistoryMessage(self.user, embed) for embed in self.messages])


def data_embed(state, *, index=None, total=None):
    title = DIBS_DATA_TITLE
    if index is not None and total is not None:
        title = f"{title} ({index}/{total})"
    embed = discord.Embed(title=title)
    payload = urllib.parse.quote(json.dumps(state))
    embed.set_footer(text="metadata", icon_url=f"{DIBS_DATA_URL}{payload}")
    return embed


def summary_embed():
    return discord.Embed(title=DIBS_SUMMARY_TITLE, description="summary")


@pytest.mark.asyncio
async def test_reconstruction_uses_only_newest_complete_snapshot(monkeypatch):
    messages = [
        summary_embed(),
        data_embed(
            {"100": {"Air Aspect Core": 2}, "200": {"Command Aspect Core": 3}},
            index=2,
            total=2,
        ),
        data_embed({"100": {"Void Aspect Core": 1}}, index=1, total=2),
        summary_embed(),
        data_embed({"999": {"Removed claim": 1}}),
    ]
    monkeypatch.setattr(main, "DIBS_CHANNEL_ID", "123")
    tracker = main.DibsTracker(items_csv="missing-items.csv")

    await tracker.reconstruct_from_history(HistoryBot(messages))

    assert tracker.dibs == {
        100: {"Void Aspect Core": 1, "Air Aspect Core": 2},
        200: {"Command Aspect Core": 3},
    }


@pytest.mark.asyncio
async def test_reconstruction_falls_back_from_incomplete_newest_snapshot(monkeypatch):
    messages = [
        data_embed({"100": {"Partial claim": 1}}, index=1, total=2),
        summary_embed(),
        data_embed({"300": {"Stable claim": 3}}),
    ]
    monkeypatch.setattr(main, "DIBS_CHANNEL_ID", "123")
    tracker = main.DibsTracker(items_csv="missing-items.csv")

    await tracker.reconstruct_from_history(HistoryBot(messages))

    assert tracker.dibs == {300: {"Stable claim": 3}}


@pytest.mark.asyncio
async def test_reconstruction_falls_back_from_malformed_newest_snapshot(monkeypatch):
    malformed = discord.Embed(title=f"{DIBS_DATA_TITLE} (2/2)")
    malformed.set_footer(text="metadata", icon_url=f"{DIBS_DATA_URL}not-json")
    messages = [
        malformed,
        data_embed({"100": {"Partial claim": 1}}, index=1, total=2),
        summary_embed(),
        data_embed({"400": {"Stable claim": 4}}),
    ]
    monkeypatch.setattr(main, "DIBS_CHANNEL_ID", "123")
    tracker = main.DibsTracker(items_csv="missing-items.csv")

    await tracker.reconstruct_from_history(HistoryBot(messages))

    assert tracker.dibs == {400: {"Stable claim": 4}}


@pytest.mark.asyncio
async def test_reconstruction_rejects_malformed_numbered_title(monkeypatch):
    malformed = data_embed({"100": {"Partial claim": 1}})
    malformed.title = f"{DIBS_DATA_TITLE} (3/2)"
    messages = [
        malformed,
        summary_embed(),
        data_embed({"500": {"Stable claim": 5}}),
    ]
    monkeypatch.setattr(main, "DIBS_CHANNEL_ID", "123")
    tracker = main.DibsTracker(items_csv="missing-items.csv")

    await tracker.reconstruct_from_history(HistoryBot(messages))

    assert tracker.dibs == {500: {"Stable claim": 5}}
