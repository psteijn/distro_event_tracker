#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  python3 -m venv "$ROOT_DIR/.venv"
fi

"$PYTHON" -m pip install --disable-pip-version-check -q -e "$ROOT_DIR[dev]"
cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR/src"
"$PYTHON" -m black --check src tests
"$PYTHON" -m ruff check src tests
"$PYTHON" -m mypy
"$ROOT_DIR/.venv/bin/lint-imports"
"$PYTHON" -m pytest --cov=distro_event_tracker --cov-report=term-missing tests
