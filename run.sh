#!/bin/bash
poetry install
poetry run gunicorn 'server_browser_backend:main(graylog_host="logs.jacoby6000.com")' "$@"
