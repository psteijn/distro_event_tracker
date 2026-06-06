#!/bin/bash
set -euo pipefail

source "${BASH_SOURCE[0]%/*}/init.sh"

python -m pip install -q -r requirements-dev.txt
python -m black --check src tests
python -m ruff check src tests
python -m mypy
export PYTHONPATH="${BASH_SOURCE[0]%/*}/src"
lint-imports
python -m pytest --cov=distro_event_tracker --cov-report=term-missing tests
