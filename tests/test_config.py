import pytest

from distro_event_tracker import config
from distro_event_tracker.config import validate_event_command_name


@pytest.mark.parametrize("name", ["event", "ocean", "ocean-distro", "ocean_distro", "event2"])
def test_validate_event_command_name_accepts_valid_names(name):
    assert validate_event_command_name(name) == name


@pytest.mark.parametrize("name", ["", "Distro", "ocean distro", "x" * 33, "distro!"])
def test_validate_event_command_name_rejects_invalid_names(name):
    with pytest.raises(ValueError, match="EVENT_COMMAND_NAME must be 1-32 characters"):
        validate_event_command_name(name)


def test_settings_exposes_optional_planning_channel(monkeypatch):
    monkeypatch.setattr(config, "PLANNING_CHANNEL_ID", "123456")

    assert config.load_settings().planning_channel_id == "123456"
