#!/usr/bin/env sh
# HR-MIS launcher for macOS / Linux
cd "$(dirname "$0")" || exit 1
exec python3 run.py "$@"
