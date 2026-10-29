# Server browser backend

This is a flask based python server which has its routes defined in OpenAPI spec [here](./assets/chiv2-server-browser-api.yaml).

## Running the server 

### Docker
The preferred method for running this server is via docker.

```
HOST_CONFIG_DIR=$(pwd)/config
docker run \
  -p 8080:8080 \
  -e ADMIN_KEY='YOUR_SECRET_KEY_FOR_MANAGING_BANS' \
  -e CONFIG_DIR='/config' \
  -e GUNICORN_WORKERS=4 \
  -v $HOST_CONFIG_DIR:/config \
  -it \
  ghcr.io/chiv2-community/c2serverbrowserbackend:latest
```

The server can be configured using environment variables:
- `ADMIN_KEY`: The key used for administrative actions (e.g. banning).
- `CONFIG_DIR`: The directory where configuration files are stored (e.g. `allow_list.txt`, `ban_list.txt`).
- `SERVER_BROWSER_FQDN`: The FQDN of the server, used as the issuer for reissued tokens (default: `chivalry2-server-browser-backend`).
- `GUNICORN_BIND`: The host and port gunicorn should bind to (default: `0.0.0.0:8080`).
- `GUNICORN_WORKERS`: The number of gunicorn workers (default: `1`).
- `GUNICORN_THREADS`: The number of gunicorn threads (default: `1`).
- `GUNICORN_LOG_LEVEL`: The gunicorn log level (default: `info`).
- `GUNICORN_TIMEOUT`: The gunicorn timeout in seconds (default: `30`).
- `EXPOSE_REGISTERED_IPS`: Set to `1` to include observed and advertised IP
  fields in `/api/v1/servers` for diagnostics; omitted by default.

Any additional arguments passed to the docker run command will be passed directly to gunicorn.

### Dual-stack IPv4/IPv6 binding

Keep the default `0.0.0.0:8080` bind for IPv4-only deployments. On a normal
Linux dual-stack host, run Gunicorn with one IPv6 wildcard listener:

```bash
GUNICORN_BIND='[::]:8080' ./run.sh
```

This accepts IPv6 and IPv4-mapped connections when the host's IPv6 socket mode
allows it. Confirm with `ss -ltnp` and allow TCP 8080 for both address families.
If the host uses IPv6-only sockets, pass separate Gunicorn `--bind` arguments
instead of relying on the wildcard socket.


Will run the latest server and run on port 8080

### UV
This is a [uv](https://docs.astral.sh/uv/) project, and as such dependencies are managed via `uv`.

Then the project can be run via `./run.sh`

Try running with `--help` to see what options are available.

Tests can be run via `./ci.sh`

See [CONTRIBUTING.md](CONTRIBUTING.md) for publishing instructions.
