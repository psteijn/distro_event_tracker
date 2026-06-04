import pytest
import csv
from main import DibsTracker


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


def test_remove_dib():
    tracker = DibsTracker()
    tracker.add_dib(123, "Command Aspect Core", 5)
    tracker.add_dib(123, "Void Aspect Core", "all")

    assert tracker.remove_dib(123, "Command Aspect Core") is True
    assert "Command Aspect Core" not in tracker.dibs[123]
    assert "Void Aspect Core" in tracker.dibs[123]

    assert tracker.remove_dib(123, "Void Aspect Core") is True
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

    data_str = tracker.get_summary_data()

    new_tracker = DibsTracker()
    new_tracker.load_from_summary_data(data_str)

    assert new_tracker.dibs[123]["Command Aspect Core"] == 5
    assert new_tracker.dibs[456]["Void Aspect Core"] == "all"
    assert isinstance(list(new_tracker.dibs.keys())[0], int)


@pytest.mark.asyncio
async def test_reconstruct_from_history_link_based():
    import urllib.parse
    import main

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
    import main

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
    import main

    tracker = main.DibsTracker()
    tracker.add_dib(555, "Air Aspect Core", 3)
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

