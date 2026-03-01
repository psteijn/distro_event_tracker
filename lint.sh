#!/bin/bash

# Discord Event Tracker Bot – lint/format (Black + Ruff)
echo "========================================"
echo "  Lint (Black + Ruff)"
echo "========================================"
echo

source "${BASH_SOURCE[0]%/*}/init.sh"

echo "Installing lint tools if needed..."
pip install -q -r requirements-dev.txt
if [ $? -ne 0 ]; then
    echo "ERROR: pip install -r requirements-dev.txt failed"
    exit 1
fi

# In CI: check only. Locally: fix.
if [ "${GITHUB_ACTIONS}" = "true" ] || [ "${CI}" = "true" ]; then
    echo
    echo "--- Black (format check) ---"
    black --check .
    EXIT=$?
    if [ $EXIT -ne 0 ]; then
        echo "Black failed. Format with: black ."
        exit $EXIT
    fi
    echo "Black OK."

    echo
    echo "--- Ruff (lint) ---"
    ruff check .
    EXIT=$?
    if [ $EXIT -ne 0 ]; then
        exit $EXIT
    fi
    echo "Ruff OK."
else
    echo
    echo "--- Black (format) ---"
    black .
    if [ $? -ne 0 ]; then
        exit 1
    fi
    echo "Black done."

    echo
    echo "--- Ruff (lint fix) ---"
    ruff check . --fix
    if [ $? -ne 0 ]; then
        exit 1
    fi
    echo "Ruff done."
fi

echo
echo "✅ Lint completed successfully."
