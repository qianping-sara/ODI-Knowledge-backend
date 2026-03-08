#!/usr/bin/env bash
set -euo pipefail

uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
