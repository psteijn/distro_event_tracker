from distro_event_tracker import bot as main


def test_register_dibs_tree_command_skips_when_channel_missing(monkeypatch):
    monkeypatch.setattr(main, "DIBS_CHANNEL_ID", "")

    called = {"value": False}

    def fake_command(*args, **kwargs):
        called["value"] = True

        def decorator(func):
            return func

        return decorator

    monkeypatch.setattr(main.bot.tree, "command", fake_command)

    @main.register_dibs_tree_command(name="dibs")
    def sample():
        return "ok"

    assert sample() == "ok"
    assert called["value"] is False
