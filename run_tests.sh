#!/bin/bash

# Discord Event Tracker Bot Tests Script for Windows (Git Bash/WSL)
echo "========================================"
echo "  Discord Event Tracker Tests"
echo "========================================"
echo

source "${BASH_SOURCE[0]%/*}/init.sh"

echo "Running tests..."
echo

python -m pytest tests/

echo "Tests completed"
