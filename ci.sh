#!/bin/bash
set -euo pipefail

uv sync --frozen --all-packages
uv run server-browser-codegen --check
uv run mypy
DEBUG_MODE=true uv run pytest
uv build --all-packages
uv run python scripts/check_wheels.py
