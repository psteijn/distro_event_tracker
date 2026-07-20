from distro_event_tracker import healthcheck


class FakeResponse:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


def test_healthcheck_succeeds_for_ready_endpoint(monkeypatch):
    monkeypatch.setattr(
        healthcheck.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(200),
    )
    assert healthcheck.main() == 0


def test_healthcheck_fails_when_endpoint_is_unavailable(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise OSError("unavailable")

    monkeypatch.setattr(healthcheck.urllib.request, "urlopen", unavailable)
    assert healthcheck.main() == 1
