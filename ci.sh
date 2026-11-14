#!/bin/bash
set -euo pipefail

uv sync --frozen --all-packages
uv run server-browser-codegen --check
uv run mypy
DEBUG_MODE=true uv run pytest
uv build --all-packages
uv run python scripts/check_wheels.py
cargo test --locked --manifest-path sdk/rust/Cargo.toml --workspace
uv run python scripts/check_rust_sdk.py
cargo package --locked --manifest-path sdk/rust/Cargo.toml --workspace --allow-dirty
