#!/bin/bash
set -euo pipefail

uv sync --frozen --all-packages
uv run python scripts/generate_api.py --check
uv run mypy src packages/server-browser-api/src scripts
DEBUG_MODE=true uv run pytest
uv build --all-packages
uv run python scripts/check_wheels.py
