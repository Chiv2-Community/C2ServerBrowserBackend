# Server browser backend

This is a FastAPI server with OAS-generated models, interfaces, and routes.
The contract is [here](./assets/chiv2-server-browser-api.yaml).

## Running the server 

### Docker
The preferred method for running this server is via docker.

```
HOST_CONFIG_DIR=$(pwd)/config
docker run \
  -p 8080:8080 \
  -e ADMIN_KEY='YOUR_SECRET_KEY_FOR_MANAGING_BANS' \
  -e CONFIG_DIR='/config' \
  -e UVICORN_WORKERS=1 \
  -v $HOST_CONFIG_DIR:/config \
  -it \
  ghcr.io/chiv2-community/c2serverbrowserbackend:latest
```

The server can be configured using environment variables:
- `ADMIN_KEY`: The key used for administrative actions (e.g. banning).
- `CONFIG_DIR`: The directory where configuration files are stored (e.g. `allow_list.txt`, `ban_list.txt`).
- `SERVER_BROWSER_FQDN`: The FQDN of the server, used as the issuer for reissued tokens (default: `chivalry2-server-browser-backend`).
- `UVICORN_HOST`: Listener address (default: `0.0.0.0`).
- `UVICORN_PORT`: Listener port (default: `8080`).
- `UVICORN_WORKERS`: Worker processes (default: `1`). Keep one worker while
  registrations and signing keys are process-local; multiple workers do not share them.
- `UVICORN_LOG_LEVEL`: Log level (default: `info`).
- `UVICORN_KEEP_ALIVE`: Idle HTTP keep-alive timeout in seconds (default: `5`),
  not a request execution timeout.
- `EXPOSE_REGISTERED_IPS`: Set to `1` to include observed and advertised IP
  fields in `/api/v1/servers` for diagnostics; omitted by default.

Container arguments are passed directly to Uvicorn. Gunicorn and its
`GUNICORN_*` settings are no longer used; migrate deployment settings above.
There is no equivalent of Gunicorn's worker request timeout or thread setting.

### IPv6 and reverse proxies

The default listener is IPv4. To listen on IPv6:

```bash
./run.sh --host ::
```

For Docker, set `UVICORN_HOST=::`. Do not assume an IPv6 listener accepts IPv4;
use a dual-stack reverse proxy and verify both address families.

As before, deploy behind one trusted proxy that overwrites `X-Forwarded-*`
headers and blocks direct backend access. The application trusts the last
forwarded client IP. Startup disables Uvicorn's separate proxy processing to
avoid interpreting the headers twice.

### UV
This is a [uv](https://docs.astral.sh/uv/) project, and as such dependencies are managed via `uv`.

Then the project can be run via `./run.sh`

Try running with `--help` to see what options are available.

Tests can be run via `./ci.sh`

The API is OpenAPI-first. Models, API interfaces, and FastAPI bindings are generated
into a separate uv workspace package. See [API development](CONTRIBUTING.md#api-development)
for generation, interface implementation, and multi-package builds.

See [CONTRIBUTING.md](CONTRIBUTING.md) for publishing instructions.
