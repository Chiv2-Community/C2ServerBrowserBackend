#!/bin/bash

poetry update
poetry run python src/mock_chiv2_host/mock_host.py "$@"
