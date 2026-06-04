import pytest
import csv
from main import DibsTracker


@pytest.fixture
def temp_items_csv(tmp_path):
    csv_file = tmp_path / "test_items.csv"
    with open(csv_file, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["item_name"])
        writer.writerow(["Command Aspect Core"])
        writer.writerow(["Void Aspect Core"])
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
