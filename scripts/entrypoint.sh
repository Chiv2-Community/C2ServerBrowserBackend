#!/bin/bash
set -euo pipefail

exec uvicorn server_browser_backend.main:app \
    --host "${UVICORN_HOST:-0.0.0.0}" \
    --port "${UVICORN_PORT:-8080}" \
    --workers "${UVICORN_WORKERS:-1}" \
    --log-level "${UVICORN_LOG_LEVEL:-info}" \
    --timeout-keep-alive "${UVICORN_KEEP_ALIVE:-5}" \
    --no-proxy-headers \
    "$@"
