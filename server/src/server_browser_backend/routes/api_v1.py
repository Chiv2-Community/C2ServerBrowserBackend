from __future__ import annotations
import json
from typing import Callable, Dict, List, Optional, Tuple, TypeVar
from flask import Flask, Blueprint, request, jsonify, Request, send_file, send_from_directory
from datetime import datetime, timedelta
import argparse
from uuid import uuid4
from server_browser_backend import dict_util
from server_browser_backend.server_list import (
    InvalidSecretKey,
    SecretKeyMissing,
)
from os import getenv

from server_browser_backend.models import UpdateRegisteredServer, Server
from server_browser_backend.dict_util import DictKeyError, DictTypeError, get_list_or
from logging.config import dictConfig

from server_browser_backend.routes.shared import KEY_HEADER, Banned, get_and_validate_ip, get_key, server_list, ADMIN_KEY_HEADER, ban_list

from flask import current_app


api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

@api_v1_bp.route("/swagger.yaml")
def send_swagger():
    get_and_validate_ip()
    return send_file("../../assets/chiv2-server-browser-api.yaml")

@api_v1_bp.route("/servers", methods=["POST"])
def register():
    server_ip = get_and_validate_ip()

    # Insert inferred params in to the json so we can build the server object from json.
    # Not the prettiest, but simplifies construction somewhat
    request.json["unique_id"] = str(uuid4())
    request.json["ip_address"] = server_ip
    request.json["last_heartbeat"] = datetime.now().timestamp()

    server = Server.from_json(request.json)
    key = server_list.register(server)
    timeout = server.last_heartbeat + server_list.heartbeat_timeout

    current_app.logger.info(
        f'Registered server "{server.name}" at {server.ip_address}:{server.ports.game}'
    )

    return jsonify({"refresh_before": timeout, "key": key, "server": server}), 201



@api_v1_bp.route("/servers/<server_id>/heartbeat", methods=["POST"])
def heartbeat(server_id: str):
    get_and_validate_ip()
    return update_server(
        server_id,
        lambda server: server.with_heartbeat(datetime.now().timestamp()),
    )


@api_v1_bp.route("/servers/<server_id>", methods=["PUT"])
def update(server_id: str):
    get_and_validate_ip()
    if not request.json:
        return (
            jsonify(
                {"status": "invalid_json_body", "message": "no json body provided"}
            ),
            400,
        )

    request_json = request.json

    return update_server(
        server_id,
        lambda server: server.with_update(
            UpdateRegisteredServer.from_json(request_json)
        ),
    )


@api_v1_bp.route("/servers", methods=["GET"])
def get_servers():
    get_and_validate_ip()
    servers = server_list.get_all()
    return jsonify({"servers": servers}), 200

ADMIN_KEY = getenv("ADMIN_KEY")

def validate_admin_key(input: str):
    if ADMIN_KEY is None:
        return False

    return input == ADMIN_KEY

@api_v1_bp.route("/admin/ban-list", methods=["POST"])
def add_to_ban_list():
    sent_admin_key = request.headers.get(ADMIN_KEY_HEADER)
    if not validate_admin_key(sent_admin_key):
        return jsonify({}), 403
    
    ip_list = get_list_or(request.json, "ban_ips", str)
    current_app.logger.info(f"Adding addresses to ban_list: {ban_list}")

    ban_list.extend(ip_list)

    return jsonify({"banned_ips": ban_list}), 200

@api_v1_bp.route("/admin/ban-list", methods=["GET"])
def get_ban_list():
    sent_admin_key = request.headers.get(ADMIN_KEY_HEADER)
    if not validate_admin_key(sent_admin_key):
        return jsonify({}), 403

    return jsonify({"banned_ips": ban_list}), 200

@api_v1_bp.errorhandler(DictKeyError)
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


@api_v1_bp.errorhandler(DictTypeError)
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


@api_v1_bp.errorhandler(SecretKeyMissing)
def handle_secret_key_missing(e):
    return (
        jsonify({"status": "no_key", "message": KEY_HEADER + " header not specified"}),
        400,
    )

@api_v1_bp.errorhandler(InvalidSecretKey)
def handle_invalid_secret_key(e):
    return jsonify({"status": "forbidden"}), 403

@api_v1_bp.errorhandler(Banned)
def handle_banned_user(e):
    return jsonify({"status": "forbidden"}), 403

def update_server(
    server_id: str, update_server: Callable[[Server], Server]
):
    key = get_key()

    if not server_list.exists(server_id):
        current_app.logger.warning(f"Update failed. Server with id {server_id} not registered.")
        return (
            jsonify({"status": "not_registered", "message": "server not registered"}),
            400,
        )

    server = server_list.update(server_id, key, update_server)

    timeout = server.last_heartbeat + server_list.heartbeat_timeout

    current_app.logger.info(
        f'Update/Heartbeat received from server "{server.name}" ({server.unique_id}) at {server.ip_address}:{server.ports.game})'
    )

    return jsonify({"refresh_before": timeout, "server": server}), 200
