#!/bin/bash
# Run the Python script with the specified flags
poetry run gunicorn "server_browser_backend:app" "$@"