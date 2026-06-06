from distro_event_tracker.events.persistence import format_event_footer, parse_event_footer


def test_event_footer_round_trip_preserves_wire_format():
    footer = format_event_footer("123_456")
    assert footer == "Event ID: 123_456"
    assert parse_event_footer(footer) == "123_456"


def test_event_footer_parser_rejects_unrelated_footer():
    assert parse_event_footer("System Metadata") is None
