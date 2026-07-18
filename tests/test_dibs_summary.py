import pytest

from distro_event_tracker import bot as main


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
