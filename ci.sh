#!/bin/bash
set -euo pipefail

uv sync --frozen --all-packages
uv run server-browser-codegen --check
uv run mypy src packages/server-browser-models/src packages/server-browser-server/src packages/server-browser-fastapi/src packages/server-browser-client/src packages/server-browser-codegen/src scripts examples
DEBUG_MODE=true uv run pytest
uv build --all-packages
uv run python scripts/check_wheels.py
