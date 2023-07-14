#!/bin/bash

poetry install --no-root
poetry run mypy src test
ADMIN_KEY=test_key poetry run pytest test
