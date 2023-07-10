from __future__ import annotations
import json
from typing import Callable, Dict, List, Optional, Tuple, TypeVar
from flask import Flask, request, jsonify, Request, send_file, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from collections import defaultdict
from datetime import datetime, timedelta
import argparse
from uuid import uuid4
from server_browser_backend import dict_util
from server_browser_backend.server_list import (
    InvalidSecretKey,
    SecretKeyMissing,
    ServerList,
)
from os import path

from server_browser_backend.models import UpdateRegisteredServer, Server
from server_browser_backend.dict_util import DictKeyError, DictTypeError
from server_browser_backend import tbio
from server_browser_backend import playfab
from logging.config import dictConfig

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s: %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://flask.logging.wsgi_errors_stream",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["wsgi"]},
    }
)

KEY_HEADER = "x-chiv2-server-browser-key"

# Later defined in main
ban_list_location: str = ""
ban_list: List[str] = []

app = Flask(__name__)
limiter = Limiter(app=app, key_func=get_remote_address)


# 1 minute timeout for heartbeats
heartbeat_timeout = 65

servers: ServerList = ServerList(heartbeat_timeout)


def get_ip(request) -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def get_key(request) -> str:
    key = request.headers.get(KEY_HEADER)
    if not key:
        raise SecretKeyMissing()

    return key


@app.route("/api/v1/servers", methods=["POST"])
@limiter.limit("5/minute")
def register():
    server_ip = get_ip(request)
    if server_ip in ban_list:
        return jsonify({"status": "banned"}), 403

    # Insert inferred params in to the json so we can build the server object from json.
    # Not the prettiest, but simplifies construction somewhat
    request.json["unique_id"] = str(uuid4())
    request.json["ip_address"] = server_ip
    request.json["last_heartbeat"] = datetime.now().timestamp()

    server = Server.from_json(request.json)
    key = servers.register(server)
    timeout = server.last_heartbeat + heartbeat_timeout

    app.logger.info(
        f'Registered server "{server.name}" at {server.ip_address}:{server.ports.game}'
    )

    return jsonify({"refresh_before": timeout, "key": key, "server": server}), 201


def update_server(
    request: Request, server_id: str, update_server: Callable[[Server], Server]
):
    key = get_key(request)

    if not servers.exists(server_id):
        app.logger.warning(f"Update failed. Server with id {server_id} not registered.")
        return (
            jsonify({"status": "not_registered", "message": "server not registered"}),
            400,
        )

    server = servers.update(server_id, key, update_server)

    timeout = server.last_heartbeat + heartbeat_timeout

    app.logger.info(
        f'Update/Heartbeat received from server "{server.name}" ({server.unique_id}) at {server.ip_address}:{server.ports.game})'
    )

    return jsonify({"refresh_before": timeout, "server": server}), 200


@app.route("/api/v1/servers/<server_id>/heartbeat", methods=["POST"])
@limiter.limit("10/minute")
def heartbeat(server_id: str):
    return update_server(
        request,
        server_id,
        lambda server: server.with_heartbeat(datetime.now().timestamp()),
    )


@app.route("/api/v1/servers/<server_id>", methods=["PUT"])
@limiter.limit("60/minute")
def update(server_id: str):
    if not request.json:
        return (
            jsonify(
                {"status": "invalid_json_body", "message": "no json body provided"}
            ),
            400,
        )

    request_json = request.json

    return update_server(
        request,
        server_id,
        lambda server: server.with_update(
            UpdateRegisteredServer.from_json(request_json)
        ),
    )


@app.route("/api/v1/servers", methods=["GET"])
@limiter.limit("60/minute")
def get_servers():
    server_list = servers.get_all()
    return jsonify({"servers": server_list}), 200


@app.route("/api/tbio/GetCurrentGames", methods=["POST"])
@limiter.limit("60/minute")
def tbio_get_servers():
    server_list = tbio.ServerListData.from_servers(servers.get_all())
    return jsonify(tbio.Wrapper(True, server_list)), 200

@app.route("/api/tbio/GetMotd", methods=["POST"])
@limiter.limit("60/minute")
def get_motd():
    language = dict_util.get_or(request.json, "Language", str, lambda: "en")

    language_path = f"assets/motd/{language}.json"
    default_path = f"assets/motd/en.json"

    motd_path = language_path if path.exists(language_path) else default_path

    print(path.exists(motd_path))
    with open(motd_path, "r") as f:
        motd = json.load(f)
        one_year_from_now = datetime.now() + timedelta(days=365)
        return (
            jsonify(tbio.Wrapper(True, motd, int(one_year_from_now.timestamp()))),
            200,
        )

@app.route("/api/playfab/Client/Matchmake", methods=["POST"])
@limiter.limit("60/minute")
def payfab_client_matchmake():
    server_id = request.json.get("LobbyId")
    if not server_id:
        return jsonify(playfab.Error(400, {}, "No LobbyId provided.", {}, False)), 400

    server = servers.get(server_id)

    if not server:
        return jsonify(playfab.Error(404, {}, "Lobby does not exist", {}, False)), 404

    return jsonify(playfab.Wrapper(200, "OK", playfab.Game(
        server.unique_id, 
        server.ip_address, 
        server.ip_address, 
        server.ports.game,
        str(uuid4()),
        None,
        None
    ))), 200


@app.route("/api/v1/swagger.yaml")
def send_swagger():
    return send_file("../../assets/chiv2-server-browser-api.yaml")


@app.errorhandler(DictKeyError)
def handle_dict_key_error(e):
    return (
        jsonify(
            {
                "status": "invalid_json_body",
                "message": f"Missing key '{e.key}'",
                "context": e.context,
            }
        ),
        400,
    )


@app.errorhandler(DictTypeError)
def handle_dict_type_error(e):
    error_string = f"Invalid type for key '{e.key}'. Got '{e.actual_type.__name__}' with value '{e.value}', but expected '{e.expected_type.__name__}'"
    return (
        jsonify(
            {
                "status": "invalid_json_body",
                "message": error_string,
                "context": e.context,
            }
        ),
        400,
    )


@app.errorhandler(SecretKeyMissing)
def handle_secret_key_missing(e):
    return (
        jsonify({"status": "no_key", "message": KEY_HEADER + " header not specified"}),
        400,
    )


@app.errorhandler(InvalidSecretKey)
def handle_invalid_secret_key(e):
    return jsonify({"status": "forbidden"}), 403


def main():
    parser = argparse.ArgumentParser(description="Start the Flask server.")
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="The interface to bind to."
    )
    parser.add_argument("--port", type=int, default=8080, help="The port to bind to.")
    parser.add_argument(
        "--ban-list",
        type=str,
        default="ban_list.txt",
        help="File location of line separated list of banned IPs",
    )
    args = parser.parse_args()

    ban_list_location = args.ban_list

    try:
        with open(ban_list_location) as f:
            ban_list.extend(f.read().splitlines())
    except FileNotFoundError:
        print(
            f"WARNING: Ban list file {ban_list_location} not found. Creating empty ban list file."
        )
        with open(ban_list_location, "w") as f:
            f.write("")

    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
