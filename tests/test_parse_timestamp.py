import pytest
from main import parse_timestamp, PACIFIC_TZ


def test_parse_timestamp_epoch():
    dt = parse_timestamp("1700000000")
    assert dt.tzinfo.zone == PACIFIC_TZ.zone
    # Round-trip: timestamp should match exactly
    assert int(dt.timestamp()) == 1700000000


def test_parse_timestamp_date_only():
    dt = parse_timestamp("2024-01-15")
    assert dt.year == 2024
    assert dt.month == 1
    assert dt.day == 15
    assert dt.tzinfo.zone == PACIFIC_TZ.zone
    assert dt.hour == 0
    assert dt.minute == 0
    assert dt.second == 0


def test_parse_timestamp_full_datetime():
    dt = parse_timestamp("2024-01-15 13:45:30")
    assert dt.year == 2024
    assert dt.month == 1
    assert dt.day == 15
    assert dt.hour == 13
    assert dt.minute == 45
    assert dt.second == 30
    assert dt.tzinfo.zone == PACIFIC_TZ.zone


def test_parse_timestamp_us_format():
    dt = parse_timestamp("01/15/2024")
    assert dt.year == 2024
    assert dt.month == 1
    assert dt.day == 15
    assert dt.tzinfo.zone == PACIFIC_TZ.zone


def test_parse_timestamp_invalid():
    with pytest.raises(ValueError):
        parse_timestamp("not-a-date")
