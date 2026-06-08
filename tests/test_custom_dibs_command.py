import pytest

from distro_event_tracker import bot as main


class MockResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, content, ephemeral=False):
        self.messages.append({"content": content, "ephemeral": ephemeral})


class MockInteraction:
    def __init__(self, user_id=999, user_name="Tester", channel_id=123):
        self.user = type("User", (), {"id": user_id, "name": user_name})()
        self.channel_id = channel_id
        self.guild = None
        self.response = MockResponse()


@pytest.mark.asyncio
async def test_custom_dibs_command_stores_prefixed_entry_and_refreshes(monkeypatch):
    monkeypatch.setattr(main, "DIBS_CHANNEL_ID", "123")
    main.dibs_tracker.dibs.clear()

    refreshed = {"called": False, "reason": None, "actor_name": None}

    async def fake_refresh(guild, *, reason=None, actor=None, actor_name=None, details=None):
        refreshed["called"] = True
        refreshed["reason"] = reason
        refreshed["actor_name"] = actor_name

    monkeypatch.setattr(main, "refresh_dibs_summary", fake_refresh)

    interaction = MockInteraction()
    custom_dibs_callable = getattr(main.custom_dibs, "callback", main.custom_dibs)
    await custom_dibs_callable(interaction, "Manual review note", 4)

    assert main.dibs_tracker.dibs[interaction.user.id]["__custom__:Manual review note"] == 4
    assert refreshed["called"] is True
    assert refreshed["reason"] == "custom_dibs_command"
    assert refreshed["actor_name"] == "Tester"
    assert interaction.response.messages[0]["ephemeral"] is True
    assert "Custom dibs registered" in interaction.response.messages[0]["content"]
