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
  -v $HOST_CONFIG_DIR:/config \ 
  -it \
  jacoby6000/chivalry2-unofficial-server-browser-backend:latest \
    -b 0.0.0.0:8080 \
    -w 1
```

The params passed in at the end are gunicorn arguments

Will run the latest server and run on port 8080

### Poetry
This is a poetry project, and as such dependencies are managed via poetry.  If you don't have poetry, [install it](https://python-poetry.org/docs/#installation)

Then the project can be run via `./run.sh`

Try running with `--help` to see what options are available.

Tests can be run via `./ci.sh`
