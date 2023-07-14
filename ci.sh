#!/bin/bash

poetry install --no-root
poetry run mypy .
ADMIN_KEY=test_key poetry run pytest .
