import pytest

import main
from tests.utils_discord_mocks import DummyCtx


@pytest.mark.asyncio
async def test_dibs_data_uses_resolved_usernames_and_requested_format(monkeypatch):
    main.dibs_tracker.dibs = {
        111: {"Shadow Aspect Core": 10},
        222: {"Fortune Aspect Core": "Any", "blood phylactery": 2},
    }

    class ResolvedUser:
        def __init__(self, name):
            self.name = name

    def fake_get_user(user_id):
        if user_id == 111:
            return ResolvedUser("Alpha")
        return None

    async def fake_fetch_user(user_id):
        if user_id == 222:
            return ResolvedUser("Beta")
        raise AssertionError(f"Unexpected fetch_user call for {user_id}")

    captured = {}

    async def fake_send_long_message(ctx, content, code_block=True):
        captured["ctx"] = ctx
        captured["content"] = content
        captured["code_block"] = code_block

    monkeypatch.setattr(main.bot, "get_user", fake_get_user)
    monkeypatch.setattr(main.bot, "fetch_user", fake_fetch_user)
    monkeypatch.setattr(main, "send_long_message", fake_send_long_message)

    ctx = DummyCtx()
    ctx.guild = None

    await main.dibs_data_command(ctx)

    assert captured["code_block"] is True
    assert captured["content"] == [
        "@Alpha, Shadow Aspect Core, 10",
        "@Beta, Fortune Aspect Core, Any",
        "@Beta, blood phylactery, 2",
    ]


@pytest.mark.asyncio
async def test_send_long_message_splits_on_line_boundaries():
    ctx = DummyCtx()

    async def fake_send(msg=None, embed=None):
        ctx.sent.append({"msg": msg, "embed": embed})

    ctx.send = fake_send

    lines = [f"@User, Item {i}, 1" for i in range(250)]

    await main.send_long_message(ctx, lines, code_block=False)

    assert len(ctx.sent) > 1
    assert all(entry["embed"] is None for entry in ctx.sent)
    combined_lines = []
    for entry in ctx.sent:
        assert entry["msg"] is not None
        combined_lines.extend(entry["msg"].splitlines())

    assert combined_lines == lines
