from distro_event_tracker.dibs.summary import (
    DIBS_SUMMARY_PAGE_LENGTH,
    build_dibs_summary_pages,
)


def test_summary_paginates_production_sized_claims_without_losing_lines():
    dibs = {10**17 + user: {} for user in range(18)}
    for index in range(83):
        dibs[10**17 + (index % 18)][f"Item {index:03d} with a descriptive name"] = 1

    pages = build_dibs_summary_pages(dibs)

    assert len(pages) > 1
    assert all(len(page) <= DIBS_SUMMARY_PAGE_LENGTH for page in pages)
    combined = "\n".join(pages)
    assert "**Item 000 with a descriptive name**" in combined
    assert "**Item 082 with a descriptive name**" in combined


def test_summary_splits_one_pathological_line_within_the_limit():
    dibs = {user_id: {"Shared item": 1} for user_id in range(10**17, 10**17 + 250)}

    pages = build_dibs_summary_pages(dibs, page_length=200)

    assert len(pages) > 1
    assert all(len(page) <= 200 for page in pages)
    assert sum(page.count("<@") for page in pages) == 250


def test_empty_summary_has_one_page():
    assert build_dibs_summary_pages({}) == ["No active dibs."]
