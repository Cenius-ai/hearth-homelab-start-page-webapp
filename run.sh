#!/usr/bin/env bash
# Convenience alias for start.sh (kept because the README mentions both).
set -eu
cd "$(dirname "$0")"
exec sh start.sh
