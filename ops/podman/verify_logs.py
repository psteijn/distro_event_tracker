#!/usr/bin/env python3
"""Validate fresh bot logs for a bounded deployment verification window."""

from __future__ import annotations

import argparse
import re
import sys


CONNECTION_MARKER = "has connected to Discord!"
FULL_INITIALIZATION_MARKER = "Bot fully initialized and memory reconstructed"
EVENT_MARKER = "Reconstructed event:"
FAILURE_PATTERN = re.compile(
    r"\b(?:ERROR|CRITICAL)\b|Traceback|Bot failed to start or connection lost",
    re.IGNORECASE,
)


def verify(logs: str, mode: str) -> tuple[bool, str]:
    if FAILURE_PATTERN.search(logs):
        return False, "new error-level startup signal found"
    if CONNECTION_MARKER not in logs:
        return False, "Discord connection marker not found"
    if logs.count(EVENT_MARKER) < 3:
        return False, "fewer than three reconstructed events found"
    if mode == "full" and FULL_INITIALIZATION_MARKER not in logs:
        return False, "full initialization marker not found"
    return True, "log verification passed"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fast", "full"), required=True)
    args = parser.parse_args()
    ok, message = verify(sys.stdin.read(), args.mode)
    if not ok:
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
