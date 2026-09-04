import json
import urllib.parse

import pytest

from distro_event_tracker.dibs.persistence import (
    DIBS_DATA_URL,
    build_dibs_data_chunks,
    decode_dibs_data_url,
    parse_dibs_data_block_position,
)


def test_current_data_block_titles_parse_for_single_and_paginated_snapshots():
    assert parse_dibs_data_block_position("⚙️ System Data Block") == (1, 1)
    assert parse_dibs_data_block_position("⚙️ System Data Block (2/4)") == (2, 4)


def test_malformed_data_block_titles_are_rejected():
    assert parse_dibs_data_block_position(None) is None
    assert parse_dibs_data_block_position("⚙️ System Data Block (0/4)") is None
    assert parse_dibs_data_block_position("⚙️ System Data Block (5/4)") is None
    assert parse_dibs_data_block_position("⚙️ System Data Block (two/four)") is None


def test_current_data_url_round_trips_dibs_state():
    state = {"123": {"Void Aspect Core": 2, "__custom__:Review note": "Any"}}
    url = f"{DIBS_DATA_URL}{urllib.parse.quote(json.dumps(state))}"

    assert decode_dibs_data_url(url) == {
        123: {"Void Aspect Core": 2, "__custom__:Review note": "Any"}
    }


@pytest.mark.parametrize(
    "url",
    [
        DIBS_DATA_URL,
        f"{DIBS_DATA_URL}%5B1%2C2%5D",
        f'{DIBS_DATA_URL}{urllib.parse.quote(json.dumps({"123": ["not", "claims"]}))}',
    ],
)
def test_malformed_data_urls_are_rejected(url):
    with pytest.raises(ValueError):
        decode_dibs_data_url(url)


def test_data_chunks_split_one_users_claims_and_round_trip_within_url_limit():
    state = {
        123: {f"Long custom-style claim {index:03d} with details": index for index in range(100)}
    }

    chunks = build_dibs_data_chunks(state)

    assert len(chunks) > 1
    assert all(
        len(DIBS_DATA_URL) + len(urllib.parse.quote(json.dumps(chunk))) <= 2048 for chunk in chunks
    )
    reconstructed = {}
    for chunk in chunks:
        for user_id, claims in chunk.items():
            reconstructed.setdefault(int(user_id), {}).update(claims)
    assert reconstructed == state


def test_data_chunks_reject_one_claim_that_cannot_fit():
    with pytest.raises(ValueError, match="single dibs claim"):
        build_dibs_data_chunks({123: {"x" * 3000: 1}})
