#!/bin/bash

poetry install --no-root
poetry run python src/server_browser_backend/main.py "$@"
