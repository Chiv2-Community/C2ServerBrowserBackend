#!/bin/bash
set -euo pipefail

uv sync --frozen --all-packages
uv run server-browser-codegen --check
uv run mypy
DEBUG_MODE=true uv run pytest
uv build --all-packages
uv run python scripts/check_wheels.py
cargo fmt --manifest-path sdk/rust/Cargo.toml --all -- --check
cargo clippy --locked --manifest-path sdk/rust/Cargo.toml --workspace --all-targets --all-features
cargo clippy --locked --manifest-path sdk/rust/Cargo.toml --workspace --all-targets --no-default-features --features server-browser-client/rustls-tls,server-browser-client-sdk/rustls-tls
cargo doc --locked --manifest-path sdk/rust/Cargo.toml --workspace --all-features --no-deps
cargo test --locked --manifest-path sdk/rust/Cargo.toml --workspace
cargo test --locked --manifest-path sdk/rust/Cargo.toml --workspace --release --all-features
cargo package --locked --manifest-path sdk/rust/Cargo.toml --workspace --allow-dirty
