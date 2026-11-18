$ErrorActionPreference = "Stop"
uv run --no-project python scripts/sync_versions.py --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv lock --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv lock --directory mock --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv sync --frozen --all-packages
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run server-browser-codegen --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run mypy
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$env:DEBUG_MODE = "true"
uv run pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv build --all-packages
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run python scripts/check_wheels.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run python scripts/check_rust.py --package
exit $LASTEXITCODE
