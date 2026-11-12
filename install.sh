#!/usr/bin/env bash
# Hearth installer. Installs project dependencies, creates the database and
# seeds the demo household, then exits. It never starts the web server.
set -eu
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "error: $PYTHON not found. Install Python 3.11+ first (see INSTALL.md)." >&2
  exit 1
fi

echo "==> Installing Python dependencies"
"$PYTHON" -m pip install --upgrade pip setuptools wheel
"$PYTHON" -m pip install -r requirements.txt

if [ ! -f .env ]; then
  echo "==> Creating .env from .env.example (all values are optional defaults)"
  cp .env.example .env
fi

echo "==> Creating the SQLite schema and seeding the demo household"
"$PYTHON" -m app.seed

echo "==> Verifying the application imports"
"$PYTHON" -c "import app.server; print('Hearth imports cleanly')"

echo
echo "Setup complete. Start Hearth with:  python3 -m app.server"
echo "Then open http://127.0.0.1:8000 and sign in with cenius@cenius.ai / cenius"
