#!/usr/bin/env bash
# serve.sh — T9 (MC 1164.7) local staged-serve launcher (harness scaffolding,
# NOT a deploy artifact — the shipped entrypoint is app-new/server.py).
# Starts run_local.py on 127.0.0.1:$PORT (default 8398) with a FRESH sqlite db
# and the seeded acceptance user, waits for /health, then stays attached.
set -uo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8398}"
rm -rf app-new/.data
exec ./venv/bin/python run_local.py
