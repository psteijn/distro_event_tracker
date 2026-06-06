import csv

import pytest

from distro_event_tracker import bot as main
from distro_event_tracker.bot import (
    DibsTracker,
    normalize_dibs_quantity,
    resolve_dibs_item_name,
)


@pytest.fixture
def temp_items_csv(tmp_path):
    csv_file = tmp_path / "test_items.csv"
    with open(csv_file, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Command Aspect Core", "Void Aspect Core"])
        writer.writerow(["Air Aspect Core"])
    return str(csv_file)


def test_load_items_from_csv(temp_items_csv):
    tracker = DibsTracker(items_csv=temp_items_csv)
    assert len(tracker.all_items) == 3
    assert "Command Aspect Core" in tracker.all_items
    assert "Void Aspect Core" in tracker.all_items


def test_add_dib():
    tracker = DibsTracker()
    tracker.add_dib(123, "Command Aspect Core", 5)
    assert tracker.dibs[123]["Command Aspect Core"] == 5

    # Update quantity
    tracker.add_dib(123, "Command Aspect Core", 10)
    assert tracker.dibs[123]["Command Aspect Core"] == 10


def test_normalize_dibs_quantity():
    assert normalize_dibs_quantity(None) == "Any"
    assert normalize_dibs_quantity(1) == 1
    assert normalize_dibs_quantity(7) == 7


def test_normalize_dibs_quantity_rejects_non_positive_values():
    with pytest.raises(ValueError, match="positive integer"):
        normalize_dibs_quantity(0)
    with pytest.raises(ValueError, match="positive integer"):
        normalize_dibs_quantity(-3)


def test_resolve_dibs_item_name_matches_case_insensitively(monkeypatch):
    monkeypatch.setattr(main.dibs_tracker, "all_items", ["Command Aspect Core"])

    assert resolve_dibs_item_name("command aspect core") == "Command Aspect Core"


def test_custom_dib_storage_and_resolution():
    tracker = DibsTracker()
    tracker.add_custom_dib(123, "Something Weird", 2)

    assert tracker.dibs[123]["__custom__:Something Weird"] == 2
    assert (
        DibsTracker.display_dib_item_name("__custom__:Something Weird") == "Custom: Something Weird"
    )
    assert (
        tracker.resolve_user_dib_key(123, "Custom: Something Weird") == "__custom__:Something Weird"
    )
    assert tracker.fuzzy_match_item(123, "Something Weird") == "Custom: Something Weird"


def test_remove_dib():
    tracker = DibsTracker()
    tracker.add_dib(123, "Command Aspect Core", 5)
    tracker.add_dib(123, "Void Aspect Core", "all")

    assert tracker.remove_dib(123, "Command Aspect Core") is True
    assert "Command Aspect Core" not in tracker.dibs[123]
    assert "Void Aspect Core" in tracker.dibs[123]

    assert tracker.remove_dib(123, "Void Aspect Core") is True
    assert 123 not in tracker.dibs


def test_remove_custom_dib():
    tracker = DibsTracker()
    tracker.add_custom_dib(123, "Something Weird", 2)

    assert tracker.remove_dib(123, "Custom: Something Weird") is True
    assert 123 not in tracker.dibs


def test_remove_all_dibs():
    tracker = DibsTracker()
    tracker.add_dib(123, "Command Aspect Core", 5)
    tracker.add_dib(123, "Void Aspect Core", "all")

    assert tracker.remove_all_dibs(123) is True
    assert 123 not in tracker.dibs


def test_fuzzy_match_item():
    tracker = DibsTracker()
    tracker.add_dib(123, "Command Aspect Core", 5)
    tracker.add_dib(123, "Void Aspect Core", "all")

    # Unique match
    assert tracker.fuzzy_match_item(123, "command") == "Command Aspect Core"
    assert tracker.fuzzy_match_item(123, "void") == "Void Aspect Core"

    # Ambiguous match (both have "core")
    assert tracker.fuzzy_match_item(123, "core") is None

    # No match
    assert tracker.fuzzy_match_item(123, "air") is None


def test_persistence_data_string():
    tracker = DibsTracker()
    tracker.add_dib(123, "Command Aspect Core", 5)
    tracker.add_dib(456, "Void Aspect Core", "all")
    tracker.add_custom_dib(456, "Something Weird", 2)

    data_str = tracker.get_summary_data()

    new_tracker = DibsTracker()
    new_tracker.load_from_summary_data(data_str)

    assert new_tracker.dibs[123]["Command Aspect Core"] == 5
    assert new_tracker.dibs[456]["Void Aspect Core"] == "all"
    assert new_tracker.dibs[456]["__custom__:Something Weird"] == 2
    assert isinstance(list(new_tracker.dibs.keys())[0], int)


@pytest.mark.asyncio
async def test_reconstruct_from_history_link_based():
    import urllib.parse

    from distro_event_tracker import bot as main

    tracker = main.DibsTracker()
    tracker.add_dib(123, "Command Aspect Core", 5)
    data_str = tracker.get_summary_data()
    encoded_data = urllib.parse.quote(data_str)

    # Mock classes
    class MockEmbed:
        def __init__(self):
            self.title = "‎"
            self.description = f"[‎](http://dibs.data?payload={encoded_data})"
            self.footer = None

    class MockMessage:
        def __init__(self, author):
            self.author = author
            self.embeds = [MockEmbed()]

    class MockHistory:
        def __init__(self, message):
            self.message = message

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.message:
                msg = self.message
                self.message = None
                return msg
            raise StopAsyncIteration

    class MockChannel:
        def __init__(self, message):
            self.message = message

        def history(self, limit):
            return MockHistory(self.message)

    class MockUser:
        pass

    class MockBot:
        def __init__(self):
            self.user = MockUser()

        def get_channel(self, channel_id):
            return MockChannel(MockMessage(self.user))

    # Set DIBS_CHANNEL_ID to a mock value so the function doesn't return immediately
    main.DIBS_CHANNEL_ID = "12345"

    new_tracker = main.DibsTracker()
    await new_tracker.reconstruct_from_history(MockBot())

    assert new_tracker.dibs[123]["Command Aspect Core"] == 5


@pytest.mark.asyncio
async def test_reconstruct_from_history_legacy():
    from distro_event_tracker import bot as main

    tracker = main.DibsTracker()
    tracker.add_dib(789, "Void Aspect Core", "all")
    data_str = tracker.get_summary_data()

    class MockFooter:
        def __init__(self):
            self.text = f"DATA:{data_str}"

    class MockEmbed:
        def __init__(self):
            self.title = "⚙️ Dibs System Data (DO NOT DELETE)"
            self.description = "‎"
            self.footer = MockFooter()

    class MockMessage:
        def __init__(self, author):
            self.author = author
            self.embeds = [MockEmbed()]

    class MockHistory:
        def __init__(self, message):
            self.message = message

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.message:
                msg = self.message
                self.message = None
                return msg
            raise StopAsyncIteration

    class MockChannel:
        def __init__(self, message):
            self.message = message

        def history(self, limit):
            return MockHistory(self.message)

    class MockUser:
        pass

    class MockBot:
        def __init__(self):
            self.user = MockUser()

        def get_channel(self, channel_id):
            return MockChannel(MockMessage(self.user))

    main.DIBS_CHANNEL_ID = "12345"

    new_tracker = main.DibsTracker()
    await new_tracker.reconstruct_from_history(MockBot())

    assert new_tracker.dibs[789]["Void Aspect Core"] == "all"


@pytest.mark.asyncio
async def test_reconstruct_from_history_icon_url():
    import urllib.parse

    from distro_event_tracker import bot as main

    tracker = main.DibsTracker()
    tracker.add_dib(555, "Air Aspect Core", 3)
    tracker.add_custom_dib(555, "Manual review note", 4)
    data_str = tracker.get_summary_data()
    encoded_data = urllib.parse.quote(data_str)

    class MockFooter:
        def __init__(self):
            self.text = "‎"
            self.icon_url = f"https://dibs.data?payload={encoded_data}"

    class MockEmbed:
        def __init__(self):
            self.title = "‎"
            self.description = "‎"
            self.footer = MockFooter()

    class MockMessage:
        def __init__(self, author):
            self.author = author
            self.embeds = [MockEmbed()]

    class MockHistory:
        def __init__(self, message):
            self.message = message

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.message:
                msg = self.message
                self.message = None
                return msg
            raise StopAsyncIteration

    class MockChannel:
        def __init__(self, message):
            self.message = message

        def history(self, limit):
            return MockHistory(self.message)

    class MockUser:
        pass

    class MockBot:
        def __init__(self):
            self.user = MockUser()

        def get_channel(self, channel_id):
            return MockChannel(MockMessage(self.user))

    main.DIBS_CHANNEL_ID = "12345"

    new_tracker = main.DibsTracker()
    await new_tracker.reconstruct_from_history(MockBot())

    assert new_tracker.dibs[555]["Air Aspect Core"] == 3
    assert new_tracker.dibs[555]["__custom__:Manual review note"] == 4
