$ErrorActionPreference = "Stop"
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
cargo test --locked --manifest-path sdk/rust/Cargo.toml --workspace
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
cargo package --locked --manifest-path sdk/rust/Cargo.toml --workspace --allow-dirty
exit $LASTEXITCODE
