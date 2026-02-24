#!/bin/bash

# Discord Event Tracker Bot Tests Script for Windows (Git Bash/WSL)
echo "========================================"
echo "  Discord Event Tracker Tests"
echo "========================================"
echo

source "${BASH_SOURCE[0]%/*}/init.sh"

export LOG_FILE=test_bot.log

echo "Running tests..."
echo

python -m pytest tests/
EXIT_CODE=$?

# Deactivate virtual environment
if command -v deactivate &> /dev/null; then
    deactivate
fi

if [ $EXIT_CODE -ne 0 ]; then
    echo
    echo "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    echo "  TESTS FAILED! "
    echo "  Check $LOG_FILE for detailed error logs."
    echo "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    echo
    exit $EXIT_CODE
fi

echo
echo "✅ Tests completed successfully."
