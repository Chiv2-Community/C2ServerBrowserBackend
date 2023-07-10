#!/bin/bash

poetry install
poetry run mypy .
ADMIN_KEY=test_key poetry run pytest .
