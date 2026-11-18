# Server browser SDKs

The authoritative contract is `assets/chiv2-server-browser-api.yaml`. The backend
owns generation, templates, drift checks and releases. Consumers install SDKs;
they do not carry their own schema or generation pipeline.

```text
sdk/
  python/
    server-browser-models/
    server-browser-client/
    server-browser-server/
    server-browser-fastapi/
    server-browser-codegen/
  rust/
    server-browser-models/
    server-browser-client/
    server-browser-client-sdk/
```

Python package names, imports, versions and dependency boundaries are unchanged.
See [Python packaging](../docs/python-packaging.md). Rust has generated models and
protocol bindings plus a handwritten lifecycle SDK. It has no server interfaces
or framework adapters. Python lifecycle SDK work is deferred.

## Generate and validate

```sh
uv sync --all-packages
uv run server-browser-codegen
uv run server-browser-codegen --check
./ci.sh
```

Generation uses OpenAPI Generator 7.17.0, Java 11+, and the pinned Rust toolchain
(including rustfmt) for Rust output. Tooling and module-owned
templates are bundled in `sdk/python/server-browser-codegen`, including Rust
templates. Use `--language python` or `--language rust` for one language.
Runtime consumers need neither Java nor generation tools.

## Rust consumption

All three Rust crates inherit the version in `sdk/rust/Cargo.toml`, coordinated
with Python by `.bumpversion.toml`. Dependencies pin exact sibling versions.
See [versioning](../CONTRIBUTING.md#publishing) for the bump command and tag policy.
Models depend only on serialization libraries, not an HTTP client or backend. The
async client uses reqwest and reexports the shared model module. Use the
model crate directly when no HTTP transport is needed.

Until registry name ownership and publication are configured, depend on the
backend Git URL with an exact full `rev` and `package = "server-browser-client"`
or `package = "server-browser-models"`. For lifecycle management, use
`package = "server-browser-client-sdk"`; see its [usage guide](rust/server-browser-client-sdk/README.md).
Cargo finds crates within `sdk/rust/`.
Commit the consuming application's lockfile. Never depend on a moving branch.

Inject a configured reqwest client with `apis::configuration::Configuration::with_client`.
Callers own timeouts, redirects, proxy policy and source-IP binding. Generated
configuration diagnostics are redacted. Generated errors may contain credentials
or response bodies; do not log them.
`server-browser-client` contains protocol bindings only. Registration, heartbeat,
retry and cleanup policy belongs in `server-browser-client-sdk`. Game hooks and
Discord verification remain consumer code.

## Rust build policy

- Every crate inherits workspace lints: warnings are errors, unsafe code is
  forbidden, and Clippy `all`, `pedantic`, `nursery`, and `cargo` are denied.
- Handwritten lifecycle APIs also require documentation and `Debug` implementations.
- CI checks formatting, all targets/features, rustls without native TLS, rustdoc,
  debug/release tests, and verified packages. Windows runs the Rust-only checks;
  Linux also runs the real-backend E2E suite.
- Release builds retain overflow checks and debug assertions. Dependencies and
  toolchain versions are locked; public API breaks are currently permitted.
- Generated model modules allow only named upstream-template style lints;
  handwritten code and tests retain the strict defaults. Multiple transitive
  dependency versions are allowed because HTTP/TLS dependencies select them.
- Use named fields instead of tuple-based state, fixtures, or interfaces. Standard
  library tuple-returning APIs and unit `()` remain usable.

Generated output is rustfmt-normalized during generation. Change templates or
the contract, then regenerate; do not hand-edit generated sources to satisfy lints.

Run `python scripts/check_rust.py` from the repository root for Rust-only checks.
Add `--package` to build and verify crate archives. Full CI and Windows Rust CI
share this runner so their validation steps stay aligned.
Packaging uses a fresh target directory to avoid Cargo reusing stale workspace
registry entries for unchanged package versions, then copies verified `.crate`
archives to `sdk/rust/target/package/`.

## Artifacts

CI tests both languages, builds Python wheels/sdists, exercises the Rust client
and lifecycle SDK against local Uvicorn, and runs verified Cargo workspace
packaging. Rust uses the pinned 1.93.0 toolchain. Publishing a GitHub Release
attaches Python artifacts, all three Rust `.crate` archives and the authoritative
OAS. This does not publish to PyPI or crates.io and does not create a release.

The permanent E2E suite runs generated Python sync/async clients, generated Rust
bindings and the Rust lifecycle SDK against the real Python application:

```sh
uv run pytest -q src/test/server_browser_backend/test_sdk_e2e.py
```

Binding tests cover every OAS operation and validate recorded responses against
the contract. All clients exercise IPv4/IPv6 loopback and ordinary/diagnostic
listings. IPv6 cases skip only when loopback is unavailable. Lifecycle tests
cover registration, updates, scheduled heartbeat, cancellation and cleanup;
deterministic Rust tests cover retry/recovery and ambiguous responses.

Existing released tags are immutable; their workflows/artifacts are unchanged.
No Discord service or hosted backend is needed for SDK tests.
