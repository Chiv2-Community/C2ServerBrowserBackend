#!/bin/bash
uv sync
uv run uvicorn server_browser_backend.main:app --host 0.0.0.0 --port 8080 --no-proxy-headers "$@"
