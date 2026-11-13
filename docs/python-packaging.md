# Python packages

The workspace builds five independent wheels and sdists. The OpenAPI contract
in `assets/chiv2-server-browser-api.yaml` remains authoritative.

| Distribution | Import | Responsibility |
| --- | --- | --- |
| `server-browser-models` | `server_browser_models` | Shared generated Pydantic models, strict decoding, typed IP serialization, bundled contract |
| `server-browser-client` | `server_browser_client` | Generated synchronous and asynchronous HTTPX clients |
| `server-browser-server` | `server_browser_server` | Generated abstract handler interfaces, `RequestContext`, `ApiResponse` |
| `server-browser-fastapi` | `server_browser_fastapi` | Generated routers, HTTP request decoding and response rendering |
| `chivalry2-unofficial-server-browser-backend` | `server_browser_backend` | Concrete application, registry, IP policy, token services, Uvicorn startup |

Dependencies flow from client to models, from server interfaces to models, and
from the FastAPI adapter to interfaces and models. The backend depends on the
adapter, interfaces, and models. Client code never depends on server packages.
Only the adapter and concrete backend require FastAPI. Only the backend requires
Uvicorn. Models and server interfaces require neither HTTPX nor an HTTP framework.

The four reusable packages start at version `1.0.0` and use exact internal
dependency versions. Release them together; the concrete backend retains its
own version. Package-index name ownership has not been established, and no PyPI
publication is configured. Build artifacts are usable without package-index
publication. Publishing a GitHub Release attaches the wheels, sdists, and
authoritative OpenAPI YAML; no new release is created by these changes.

## Models

```python
from server_browser_models.models import LoginRequest

request = LoginRequest.from_json({"token": "eos-token"})
```

There is one generated model implementation, shared by both transports. Strict
decoding preserves omitted-versus-null behavior. Serialization preserves aliases,
raw canonical IPs, and TBIO's exactly-once-bracketed IPv6 format.

`server_browser_models.runtime.contract()` returns the bundled OAS as a dictionary.
The same wheel contains `openapi.yaml` for non-Python tooling.

## Clients

```python
from server_browser_client import Client
from server_browser_models.models import ServerListResponse

with Client("https://browser.example") as client:
    result = client.get_servers()
    if isinstance(result.body, ServerListResponse):
        for server in result.body.servers:
            print(server.name)
```

`AsyncClient` exposes the same methods with `await` and supports `async with`.
All declared operations have generated, keyword-only parameter signatures and
typed response unions, including declared error responses.

- `result.body` is the decoded shared model, text for declared text responses,
  or `None` for an unexpected status or content type.
- `result.status`, `result.headers`, and `result.response` retain HTTP metadata
  and the full HTTPX response. HTTP errors are returned, not implicitly raised.
- Malformed declared JSON responses raise `ClientDecodeError` carrying the raw
  response. HTTPX transport errors propagate unchanged.
- Set `timeout=` explicitly when needed; the default is ten seconds. No automatic
  retries are added.
- Set `headers=` for client-scoped credentials, or supply generated header
  arguments per call. Per-call values override configured headers regardless of
  casing. Required credential headers can be omitted from a method call when
  supplied through client/session headers; the server enforces their presence.
- Pass `session=httpx.Client(...)` or `session=httpx.AsyncClient(...)` for a custom
  transport, authentication, or connection pool. Closing the SDK closes only
  sessions it constructed; callers close borrowed sessions themselves. Base URL,
  SDK timeout, and SDK headers still apply to borrowed sessions.
- Optional model fields are serialized with `exclude_unset=True`: omitted fields
  stay omitted, while explicit null remains null. Nonnullable fields must still
  satisfy the contract. Optional operation parameters use an omission sentinel;
  explicit null HTTP parameters are rejected rather than silently omitted.

## Alternative servers

Implement `BaseApiV1Api` and/or `BaseChiv2CompatApi` from
`server_browser_server.apis`. Methods receive an immutable
`RequestContext(client_ip=...)`, typed operation parameters, and return
`ApiResponse` values. These interfaces can be imported and invoked without an
HTTP framework. No global subclass registry or implicit service construction is
required.

For FastAPI, pass the implementation to the corresponding
`server_browser_fastapi.apis.*.create_router` function and include that router in
an application. The adapter converts the peer address to a context, runs the
policy hook before decoding, and executes synchronous hooks and handlers in the
thread pool. The application still owns exception mapping and trusted-proxy
policy; the backend's `application.py` is the reference wiring.

No second adapter is included. Registry, policy, and authentication services
remain internal to the concrete backend rather than becoming speculative public
packages.

## Migration

The former combined `server-browser-api` distribution/import is replaced, not
maintained as a compatibility umbrella:

- `server_browser_api.models` becomes `server_browser_models.models`.
- Abstract APIs move to `server_browser_server.apis`.
- Routers move to `server_browser_fastapi.apis`.
- Model runtime support moves to `server_browser_models.runtime`.
- `ApiResponse` and `RequestContext` live in `server_browser_server`.
- HTTP extraction/rendering helpers live in `server_browser_fastapi.runtime`.

Existing HTTP URLs, validation responses, payload casing, and backend execution
remain unchanged. Only the Python package boundary and handler context change.

Build and artifact instructions are in [CONTRIBUTING.md](../CONTRIBUTING.md).
