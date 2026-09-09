#!/usr/bin/env bash
# Development server. Connects as `calcapp` so row-level security applies.
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/uvicorn app.main:app --reload --port 8000
