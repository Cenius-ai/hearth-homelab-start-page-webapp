#!/usr/bin/env bash
# Start Hearth in the foreground. Honours PORT / APP_PORT / APP_HOST / DATA_DIR.
set -eu
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "Starting Hearth on 0.0.0.0:${PORT:-${APP_PORT:-8000}}"
exec "$PYTHON" -m app.server
