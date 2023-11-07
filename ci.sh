#!/bin/bash

poetry install --no-root
poetry run mypy src
DEBUG_MODE=true poetry run pytest
