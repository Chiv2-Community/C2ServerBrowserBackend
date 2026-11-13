# Python packaging proposal

Status: proposed; this PR does not yet change distributions or public imports.

Provide separate models, client, and server wheels so integrations can install
only what they need and alternative servers can reuse the generated contract.

## Current layout

- `server-browser-api` bundles generated models, validation, and FastAPI bindings.
  Its runtime imports FastAPI even when a consumer only needs models.
- `chivalry2-unofficial-server-browser-backend` is the concrete application. It
  depends on `server-browser-api` and provides registry, policy, and token services.
- There is no generated Python HTTP client.
- `assets/chiv2-server-browser-api.yaml` is authoritative. Generated Python is
  tracked; bundled YAML and JSON contracts are build outputs.

## Proposed distributions

Names below are proposals, not confirmed package-index availability.

| Distribution | Import | Contents | Runtime dependencies |
| --- | --- | --- | --- |
| `server-browser-models` | `server_browser_models` | Generated models, IP types, strict decoding, contract resources | Pydantic and OAS validation |
| `server-browser-client` | `server_browser_client` | Generated typed HTTP operations, response decoding, client configuration | Models and HTTP transport |
| `server-browser-server` | `server_browser_server` | Generated abstract APIs, injected FastAPI routers, request decoding, response rendering | Models and FastAPI |
| `chivalry2-unofficial-server-browser-backend` | `server_browser_backend` | Existing reference application and state services | Server bindings, Uvicorn, and application dependencies |

The three reusable packages share one model implementation. Neither the client
nor server package may generate a private copy. The concrete backend remains a
fourth distribution; installing server bindings must not install or construct it.

Dependency direction:

```text
client  -> models
server  -> models
backend -> server
```

The backend may also declare models directly when it imports them. Models must
not depend on an HTTP framework or either transport package. Client installs
must not pull in FastAPI, Uvicorn, or backend services.

## Generation and runtime boundaries

- Keep the OAS authoritative for schemas, operations, parameters, and responses.
- Generate all three reusable packages with a pinned, reproducible toolchain;
  never hand-edit generated sources.
- Move model support out of the existing mixed runtime: `WireModel`, typed IP
  serializers, model errors, schema validation, and bundled contract access.
- Keep request objects, body/parameter extraction, automatic OPTIONS handling,
  and FastAPI response rendering in the server package.
- Use transport-independent model serialization. Preserve aliases, strict
  decoding, omitted-versus-null behavior, and protocol-specific IPv6 formatting.
- Preserve generated abstract server interfaces and explicit implementation
  injection. Do not require subclasses to register themselves globally.
- Keep handwritten application orchestration outside generated packages.
- Keep backend handlers synchronous and thread-pooled; packaging is not an async
  server migration or an authentication redesign.

## Client requirements

- Cover every declared operation, including browser, admin, authentication,
  TBIO, and PlayFab compatibility endpoints.
- Accept a base URL, timeout, and caller-supplied transport/session.
- Distinguish owned and borrowed transports; closing a client must not close a
  caller-owned transport unless explicitly requested.
- Represent optional bodies and parameters without conflating omission and null.
- Decode declared success and error responses into shared models; retain HTTP
  status and headers, with raw response access for unexpected responses.
- Pass credentials per client or per call without process-global state.
- Do not introduce implicit retries for registration or other mutations.

## Builds and verification

- Build independent wheels and sdists for every distribution.
- Rebuild each wheel from its sdist outside the checkout, without Java or sibling
  source directories; runtime package dependencies can be installed separately.
- Bundle the authoritative contract with models rather than maintaining divergent
  client/server copies.
- Test models alone, client plus models, and server plus models in isolated
  environments. Verify excluded frameworks are absent, not merely unimported.
- Ship typing metadata and type-check representative downstream usage.
- Test client/server round trips with injected services, including structured
  errors, omitted/null values, and IPv4/IPv6 serialization.
- Retain generation-drift checks, backend regressions, deterministic compatibility
  replay, and real wheel startup checks.
- Update contributor build/release instructions and the release workflow for the
  final distribution set. Do not publish packages as part of this review.

## Review decisions before implementation

1. Confirm distribution/import names and whether the existing `server-browser-api`
   name needs a temporary compatibility package or an explicit migration break.
2. Choose the client transport and whether the initial client exposes synchronous,
   asynchronous, or both APIs. This does not change backend execution.
3. Confirm a shared release version for the three generated packages and their
   dependency constraints; the concrete backend can retain its own version.
4. Choose package-index publication versus wheel release assets, and verify name
   ownership before adding publication credentials or workflows.
