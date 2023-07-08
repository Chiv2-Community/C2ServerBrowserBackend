#!/bin/bash

poetry install
poetry run mypy .
poetry run pytest .
