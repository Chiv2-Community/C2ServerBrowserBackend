#!/bin/bash
# Proper signal handling
set -e

# Default values for Gunicorn configuration
BIND="${GUNICORN_BIND:-0.0.0.0:8080}"
WORKERS="${GUNICORN_WORKERS:-1}"
THREADS="${GUNICORN_THREADS:-1}"
LOG_LEVEL="${GUNICORN_LOG_LEVEL:-info}"
TIMEOUT="${GUNICORN_TIMEOUT:-30}"

# Run Gunicorn
# Use exec to ensure gunicorn receives signals (e.g., SIGTERM) from Docker directly
exec uv run gunicorn \
    --bind "$BIND" \
    --workers "$WORKERS" \
    --threads "$THREADS" \
    --log-level "$LOG_LEVEL" \
    --timeout "$TIMEOUT" \
    --access-logfile - \
    --error-logfile - \
    "server_browser_backend.main:app" \
    "$@"