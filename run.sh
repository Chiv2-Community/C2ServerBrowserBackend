#!/bin/bash
uv sync
uv run gunicorn 'server_browser_backend.main:app' "$@"
