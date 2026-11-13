$ErrorActionPreference = "Stop"
uv sync --frozen --all-packages
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run python scripts/generate_api.py --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run mypy src packages/server-browser-api/src scripts
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$env:DEBUG_MODE = "true"
uv run pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv build --all-packages
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run python scripts/check_wheels.py
exit $LASTEXITCODE
