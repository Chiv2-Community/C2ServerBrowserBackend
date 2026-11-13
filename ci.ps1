$ErrorActionPreference = "Stop"
uv sync --frozen --all-packages
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run server-browser-codegen --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run mypy src packages/server-browser-models/src packages/server-browser-server/src packages/server-browser-fastapi/src packages/server-browser-client/src packages/server-browser-codegen/src scripts examples
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$env:DEBUG_MODE = "true"
uv run pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv build --all-packages
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run python scripts/check_wheels.py
exit $LASTEXITCODE
