#!/bin/bash



poetry install
poetry run gunicorn server_browser_backend:app "$@"
