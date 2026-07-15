#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -f "backend/.venv-macos/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "backend/.venv-macos/bin/activate"
elif [ -f "backend/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "backend/.venv/bin/activate"
elif [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

python scripts/migrate_db.py
python backend/app.py
