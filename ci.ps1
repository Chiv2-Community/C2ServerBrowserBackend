poetry install --no-root
poetry run mypy src
$env:DEBUG_MODE = "true"
poetry run pytest