#!/bin/bash

uv sync
uv run mypy src
DEBUG_MODE=true uv run pytest
