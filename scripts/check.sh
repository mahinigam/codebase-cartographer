#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-backend/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" -m pytest backend/tests
"$PYTHON_BIN" -m ruff check backend/app backend/tests
"$PYTHON_BIN" -m bandit -q -r backend/app

cd frontend
npm run build
