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
  jacoby6000/chivalry2-unofficial-server-browser-backend:latest
```

The server can be configured using environment variables:
- `ADMIN_KEY`: The key used for administrative actions (e.g. banning).
- `CONFIG_DIR`: The directory where configuration files are stored (e.g. `allow_list.txt`, `ban_list.txt`).
- `GUNICORN_BIND`: The host and port gunicorn should bind to (default: `0.0.0.0:8080`).
- `GUNICORN_WORKERS`: The number of gunicorn workers (default: `1`).
- `GUNICORN_THREADS`: The number of gunicorn threads (default: `1`).
- `GUNICORN_LOG_LEVEL`: The gunicorn log level (default: `info`).
- `GUNICORN_TIMEOUT`: The gunicorn timeout in seconds (default: `30`).

Any additional arguments passed to the docker run command will be passed directly to gunicorn.

Will run the latest server and run on port 8080

### UV
This is a [uv](https://docs.astral.sh/uv/) project, and as such dependencies are managed via `uv`.

Then the project can be run via `./run.sh`

Try running with `--help` to see what options are available.

Tests can be run via `./ci.sh`
