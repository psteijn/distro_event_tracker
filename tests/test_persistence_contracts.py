from distro_event_tracker.events.persistence import (
    CREATED_BY_FIELD,
    LEGACY_BACKFILL_CREATOR_FIELD,
    format_event_footer,
    normalize_reconstructed_event_name,
    parse_event_creator_id,
    parse_event_footer,
)


def test_event_footer_round_trip_preserves_wire_format():
    footer = format_event_footer("123_456")
    assert footer == "Event ID: 123_456"
    assert parse_event_footer(footer) == "123_456"


def test_event_footer_parser_rejects_unrelated_footer():
    assert parse_event_footer("System Metadata") is None


def test_creator_parser_accepts_current_and_legacy_backfill_fields():
    assert parse_event_creator_id(CREATED_BY_FIELD, "<@123>") == 123
    assert parse_event_creator_id(LEGACY_BACKFILL_CREATOR_FIELD, "<@!456>") == 456
    assert parse_event_creator_id("Backfilled by", "<@789>") is None


def test_backfill_title_suffix_is_not_part_of_reconstructed_event_name():
    assert normalize_reconstructed_event_name("bf_123_456", "Dungeon (Backfilled)") == "Dungeon"
    assert (
        normalize_reconstructed_event_name("123_456", "Dungeon (Backfilled)")
        == "Dungeon (Backfilled)"
    )
