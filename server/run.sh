#!/bin/bash

poetry install
poetry update
poetry run python src/server_browser_backend/main.py "$@"
