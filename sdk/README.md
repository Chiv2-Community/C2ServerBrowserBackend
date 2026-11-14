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
```

Python package names, imports, versions and dependency boundaries are unchanged.
See [Python packaging](../docs/python-packaging.md). Rust has only model and
client crates; it does not generate server interfaces or framework adapters.

## Generate and validate

```sh
uv sync --all-packages
uv run server-browser-codegen
uv run server-browser-codegen --check
./ci.sh
```

Generation uses OpenAPI Generator 7.17.0 and Java 11+. Tooling and module-owned
templates are bundled in `sdk/python/server-browser-codegen`, including Rust
templates. Use `--language python` or `--language rust` for one language.
Runtime consumers need neither Java nor generation tools.

## Rust consumption

Both crates start at `1.0.0`; the client pins the exact model version. Models
depend only on serialization libraries, not an HTTP client or backend. The
blocking client uses reqwest and reexports the shared model module. Use the
model crate directly when no HTTP transport is needed.

Until registry name ownership and publication are configured, depend on the
backend Git URL with an exact full `rev` and `package = "server-browser-client"`
or `package = "server-browser-models"`. Cargo finds crates within `sdk/rust/`.
Commit the consuming application's lockfile. Never depend on a moving branch.

Inject a configured reqwest client through `apis::configuration::Configuration`.
Callers own timeouts, redirects, proxy policy and source-IP binding. Generated
errors/configuration may contain credentials or response bodies; do not log them.
Plugin transport policies, game hooks and Discord verification remain consumer
code, not generated SDK code.

## Artifacts

CI tests both languages, builds Python wheels/sdists, exercises the Rust client
against local Uvicorn, and runs verified Cargo workspace packaging. Rust uses
the pinned 1.93.0 toolchain. Publishing a GitHub Release attaches Python artifacts,
both Rust `.crate` archives and the authoritative OAS. This does not publish to
PyPI or crates.io and does not create a release.

Existing released tags are immutable; their workflows/artifacts are unchanged.
No Discord service or hosted backend is needed for SDK tests.
