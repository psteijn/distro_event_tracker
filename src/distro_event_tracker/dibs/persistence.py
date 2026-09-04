"""Stable dibs persistence contract."""

import json
import re
import urllib.parse
from collections.abc import Mapping
from typing import Any

DIBS_DATA_URL = "https://dibs.data?payload="
DIBS_LEGACY_DATA_URL = "http://dibs.data?payload="
CUSTOM_DIBS_PREFIX = "__custom__:"
DIBS_DATA_TITLE = "⚙️ System Data Block"

_DIBS_DATA_TITLE_PATTERN = re.compile(
    rf"^{re.escape(DIBS_DATA_TITLE)}(?: \(([1-9][0-9]*)/([1-9][0-9]*)\))?$"
)


def parse_dibs_data_block_position(title: str | None) -> tuple[int, int] | None:
    """Return the one-based block position encoded by current data titles."""
    if not title:
        return None
    match = _DIBS_DATA_TITLE_PATTERN.fullmatch(title)
    if not match:
        return None
    if match.group(1) is None:
        return (1, 1)

    index = int(match.group(1))
    total = int(match.group(2))
    if index > total:
        return None
    return (index, total)


def decode_dibs_data_url(url: str) -> dict[int, dict[str, Any]]:
    """Decode a current or legacy dibs payload URL into typed state."""
    parsed_url = urllib.parse.urlparse(url)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    payloads = query_params.get("payload")
    if not payloads:
        raise ValueError("Dibs data URL has no payload")

    raw_data = json.loads(payloads[0])
    if not isinstance(raw_data, dict):
        raise ValueError("Dibs payload must be a JSON object")

    decoded = {}
    for user_id, claims in raw_data.items():
        if not isinstance(claims, dict):
            raise ValueError("Each dibs user payload must be a JSON object")
        decoded[int(user_id)] = claims
    return decoded


def build_dibs_data_chunks(
    dibs: Mapping[int, Mapping[str, object]],
    *,
    max_url_length: int = 2048,
) -> list[dict[str, dict[str, object]]]:
    """Split state into payloads whose encoded URLs fit Discord's footer limit."""

    def fits(chunk: dict[str, dict[str, object]]) -> bool:
        encoded = urllib.parse.quote(json.dumps(chunk))
        return len(DIBS_DATA_URL) + len(encoded) <= max_url_length

    chunks: list[dict[str, dict[str, object]]] = []
    current: dict[str, dict[str, object]] = {}
    for user_id, claims in dibs.items():
        user_key = str(user_id)
        entries = list(claims.items()) or [(None, None)]
        for item, quantity in entries:
            candidate = {key: dict(value) for key, value in current.items()}
            candidate.setdefault(user_key, {})
            if item is not None:
                candidate[user_key][item] = quantity

            if fits(candidate):
                current = candidate
                continue

            if current:
                chunks.append(current)
            current = {user_key: {}}
            if item is not None:
                current[user_key][item] = quantity
            if not fits(current):
                raise ValueError("A single dibs claim exceeds Discord's URL length limit")

    if current or not chunks:
        chunks.append(current)
    return chunks
