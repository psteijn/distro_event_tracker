from distro_event_tracker.bot import DibsTracker
from distro_event_tracker.dibs.service import DibsAdminService


def test_admin_service_removes_standard_and_custom_claims_by_full_text():
    tracker = DibsTracker(items_csv="missing-items.csv")
    tracker.add_dib(10, "Void Aspect Core", 2)
    tracker.add_custom_dib(10, "joke request", "Any")
    service = DibsAdminService(tracker)

    result = service.remove_for_member(10, "JOKE request")

    assert result.changed is True
    assert result.display_item == "Custom: joke request"
    assert tracker.dibs[10] == {"Void Aspect Core": 2}


def test_admin_service_does_not_fuzzy_match_claim_text():
    tracker = DibsTracker(items_csv="missing-items.csv")
    tracker.add_dib(10, "Void Aspect Core", 2)
    tracker.add_custom_dib(10, "joke request", "Any")

    result = DibsAdminService(tracker).remove_for_member(10, "joke")

    assert result.changed is False
    assert len(tracker.dibs[10]) == 2


def test_admin_service_can_clear_a_members_dibs_or_report_no_match():
    tracker = DibsTracker(items_csv="missing-items.csv")
    tracker.add_dib(10, "Void Aspect Core", 2)
    tracker.add_dib(10, "Air Aspect Core", 1)
    service = DibsAdminService(tracker)

    assert service.remove_for_member(10, "missing").changed is False

    result = service.remove_for_member(10, "all")

    assert result.changed is True
    assert result.removed_claims == 2
    assert 10 not in tracker.dibs


def test_admin_service_reset_clears_every_member_without_item_reload():
    tracker = DibsTracker(items_csv="missing-items.csv")
    tracker.all_items = ["Existing catalog item"]
    tracker.add_dib(10, "Void Aspect Core", 2)
    tracker.add_dib(20, "Air Aspect Core", 1)

    result = DibsAdminService(tracker).reset()

    assert result.changed is True
    assert result.removed_claims == 2
    assert result.removed_members == 2
    assert tracker.dibs == {}
    assert tracker.all_items == ["Existing catalog item"]
