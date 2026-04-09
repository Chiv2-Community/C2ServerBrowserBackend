#!/bin/bash

uv sync
uv run python src/mock_chiv2_host/mock_host.py "$@"
