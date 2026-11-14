# Server browser code generation

Development-only uv workspace project. It owns the pinned OpenAPI Generator
toolchain, generation CLI, configuration, templates, and generation tests.
Runtime SDK packages and the backend do not depend on it.

From the repository root:

```bash
uv sync --all-packages
uv run server-browser-codegen
uv run server-browser-codegen --check
uv run server-browser-codegen --language rust --check
```

The installed wheel also supports
`python -m server_browser_codegen --root /path/to/repository --check` from outside
the checkout. Generation requires Java 11 or newer; building and installing this
tool's wheel does not. The tool bundles its configuration and templates, not a
second copy of the authoritative OpenAPI contract.

## Ownership

All templates live under `src/server_browser_codegen/templates/`:

| Directory | Output owner |
| --- | --- |
| `models/` | `server_browser_models` models, exports, and model runtime |
| `client/` | `server_browser_client` typed clients, exports, and HTTPX runtime |
| `server/` | `server_browser_server` abstract interfaces, exports, and context/response types |
| `fastapi/` | `server_browser_fastapi` routers, exports, and HTTP runtime |
| `shared/` | Common packaging markers (`py.typed`) |
| `rust/models/` | Rust model crate, manifest, and `anyOf` decoding |
| `rust/client/` | Rust client crate manifest and external-model exports |

`config.yaml` maps supporting templates to their explicit generated output paths.
OpenAPI Generator requires three entry-point filenames (`model.mustache`,
`base_api.mustache`, `api.mustache`) at its template root. The CLI creates aliases
only in a temporary staging directory; source templates stay with their owners.
No top-level template forwarding files are needed in the repository.

Edit the authoritative contract in `assets/chiv2-server-browser-api.yaml` for
API changes. Edit this project's templates for generation behavior. Never edit
generated SDK sources. `--check` generates into temporary storage and compares
all Python and Rust output packages without modifying them. Use `--language python`
or `--language rust` to select one language; the default is `all`. Python outputs
live in `sdk/python/`; Rust outputs live in `sdk/rust/` and contain only models
and clients. Handwritten tests/examples are outside generated `src/` directories.
The separate Rust `server-browser-client-sdk` crate is handwritten and is never
an output of generation.
