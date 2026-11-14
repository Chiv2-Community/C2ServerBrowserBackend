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
  Empty or non-ASCII keys fail startup. Use a long, randomly generated ASCII key.
- `TRUSTED_PROXY_CIDRS`: Comma-separated proxy IPs/CIDRs allowed to supply
  `X-Forwarded-*`. Defaults to `127.0.0.1/32,::1/128`; empty disables trust.
  For a container proxy, configure its actual backend-facing address/network.
  Do not include untrusted clients or public catch-all networks.
- `MAX_REGISTERED_SERVERS`: Global registration cap; defaults to 1,024.
- `MAX_REGISTERED_SERVERS_PER_IP`: Per-source-IP registration cap; defaults to 16.
  Both caps must be positive integers. Hosts sharing a public IP share its cap.
- `CONFIG_DIR`: The directory where configuration files are stored (e.g. `allow_list.txt`, `ban_list.txt`).
- `DISCORD_SIGNING_KEYRING`: Path to an explicitly provisioned persistent signing
  keyring. Unset publishes an empty JWKS; an invalid configured path fails startup.
- `UVICORN_HOST`: Listener address (default: `0.0.0.0`).
- `UVICORN_PORT`: Listener port (default: `8080`).
- `UVICORN_WORKERS`: Worker processes (default: `1`). Keep one worker while
  registrations and signing keys are process-local; multiple workers do not share them.
- `UVICORN_LOG_LEVEL`: Uvicorn startup/access log level (default: `info`).
- `UVICORN_KEEP_ALIVE`: Idle HTTP keep-alive timeout in seconds (default: `5`),
  not a request execution timeout.
- `EXPOSE_REGISTERED_IPS`: Set to `1` to include observed and advertised IP
  fields in `/api/v1/servers` for diagnostics; omitted by default.

Container arguments are passed directly to Uvicorn. Gunicorn and its
`GUNICORN_*` settings are no longer used; migrate deployment settings above.
There is no equivalent of Gunicorn's worker request timeout or thread setting.

### Discord authentication (development)

Discord signing/JWKS and internal session-storage foundations are available,
but OAuth/session APIs and game admission are not yet implemented. See
[Discord authentication](docs/discord-auth.md) for provisioning, rotation,
storage limits, and rollout gates.

### Logs

Application and Uvicorn console logs share
`DATE | LEVEL | REQUESTOR IP | NS - message`, with
the level right-padded or truncated to exactly five characters (`INFO `,
`WARNI`, `CRITI`). `NS` is the logger name, for example
`uvicorn.access` or `server_browser_backend.routes.api_v1`.
The IP follows the existing forwarded-header policy; outside HTTP requests it
is `-`. Invalid IP values also render as `-`. The IP field is right-padded to
at least 15 characters; longer IPv6 addresses are not truncated.

Follow the service's startup, HTTP access, and application logs with:

```bash
docker compose logs --tail=100 -f server-browser
```

Application logs use INFO for startup, registrations, accepted updates/heartbeats,
deletions, registry expiry, and IP-list changes. WARNING identifies host changes,
invalidated registrations, missing/invalid keys, unknown registrations, and
rejected administration/validation requests, and banned requesters. Unexpected
failures log ERROR with request context and a traceback. Host-change detection
is logged before checking the key; invalidation is logged only after an
authorized deletion succeeds.

Events include server IDs and requester addresses when available. These addresses
appear in operational logs even when `EXPOSE_REGISTERED_IPS` is off. Protect log
access accordingly. Lifecycle/rejection messages do not dump credentials,
tokens, request bodies, or query strings. Error tracebacks contain exception
details, and Uvicorn access logs still contain requested URLs.

Application events stay at INFO independently of `UVICORN_LOG_LEVEL`. Optional
`GRAYLOG_HOST` and `GRAYLOG_PORT` (default: `12201`) additionally send application
events to Graylog over TCP; console logging remains enabled. Uvicorn keeps its
own console handlers and log-level settings.

### IPv6 and reverse proxies

The default listener is IPv4. To listen on IPv6:

```bash
./run.sh --host ::
```

For Docker, set `UVICORN_HOST=::`. Do not assume an IPv6 listener accepts IPv4;
use a dual-stack reverse proxy and verify both address families.

Deploy behind one trusted proxy that overwrites `X-Forwarded-*` headers and
blocks direct backend access. Only peers in `TRUSTED_PROXY_CIDRS` may supply
forwarded values; other peers cannot override their IP or scheme. The application
uses the last forwarded IP when valid and accepts only `http`/`https` schemes. Startup
disables Uvicorn's separate proxy processing to avoid interpreting headers twice.

JSON bodies are limited to 1 MiB, including chunked requests. Larger bodies
return HTTP 413. Invalid Unicode strings or more than 64 object/array levels
(including the root) return HTTP 400 before model decoding or state changes.
Uploads have a total ten-second deadline, regardless of chunk activity. Expiry
returns HTTP 408 and closes HTTP/1.x connections; incomplete bodies change no state.
Keep proxy request timeouts and connection/concurrency limits;
the body cap does not bound slow clients or total concurrent memory use.

Registration quotas return HTTP 429 without evicting live servers. Expired
registrations are reclaimed on registration/listing; deletion also frees capacity.
Registration and update metadata follows OAS limits: 256 characters for server
names/maps, 4,096 for descriptions, and 64 mods with bounded name/organization/
version strings. Player counts and capacities must be between 0 and 1,024;
this also bounds the synthetic player-ID lists in TBIO responses.
Keep proxy rate limits; quotas bound retained state, not request
rate or CPU use. The registry remains process-local: use one backend worker.

IPv4-mapped IPv6 addresses use their IPv4 identity for bans, verified status,
proxy trust, and per-IP quotas. Mapped CIDRs within `::ffff:0:0/96` are stored as
IPv4 CIDRs; equivalent forms can remove the same entry. Native IPv6 stays
separate: `::/0` does not grant IPv4 verified status or proxy trust.

Verified/official flags in listings and update responses reflect the current
verified-IP policy, including changes to already registered servers.
Policy-list mutations are serialized within one application instance and use
private temporary files and atomic replacement. Failed writes before replacement
leave the active policy unchanged. If the final directory flush fails after
replacement, the change is already active but crash durability is uncertain;
read back the list before retrying. Keep policy files in a private directory,
and do not run independent writers or multiple backend workers against them.

### UV
This is a [uv](https://docs.astral.sh/uv/) project, and as such dependencies are managed via `uv`.

Then the project can be run via `./run.sh`

Try running with `--help` to see what options are available.

Tests can be run via `./ci.sh`

The API is OpenAPI-first. Models, API interfaces, and FastAPI bindings are generated
into a separate uv workspace package. See [API development](CONTRIBUTING.md#api-development)
for generation, interface implementation, and multi-package builds.

See [CONTRIBUTING.md](CONTRIBUTING.md) for publishing instructions.
