from __future__ import annotations

from datetime import datetime
from typing import Callable
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request, send_file

from server_browser_backend.dict_util import DictKeyError, DictTypeError, get_list_or
from server_browser_backend.models.base_models import Server, UpdateRegisteredServer
from server_browser_backend.routes import shared
from server_browser_backend.routes.shared import Banned, get_and_validate_ip, get_key
from server_browser_backend.server_list import InvalidSecretKey, SecretKeyMissing

import traceback

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
    if not shared.is_whitelisted():
        server = server.unverified()

    key = shared.server_list.register(server)
    timeout = server.last_heartbeat + shared.server_list.heartbeat_timeout

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


@api_v1_bp.route("/servers/<server_id>", methods=["DELETE"])
def delete_server(server_id: str):
    get_and_validate_ip()
    key = get_key()

    server = shared.server_list.delete(server_id, key)
    if server is None:
        current_app.logger.warning(
            f"Deletion failed. Server with id {server_id} not registered."
        )
        return (
            jsonify({"status": "not_registered", "message": "server not registered"}),
            404,
        )

    current_app.logger.info(
        f'Deleted server with id "{server.name}" at {server.ip_address}:{server.ports.game}'
    )
    return (
        jsonify({"status": "deleted", "message": "The server has been deleted"}),
        200,
    )


@api_v1_bp.route("/servers", methods=["GET"])
def get_servers():
    get_and_validate_ip()
    servers = shared.server_list.get_all()
    server_listing_servers = [x.to_server_response() for x in servers]
    return jsonify({"servers": server_listing_servers}), 200


@api_v1_bp.route("/admin/ban-list", methods=["PUT"])
def add_to_ban_list():
    source_ip = get_and_validate_ip()

    sent_admin_key = request.headers.get(shared.ADMIN_KEY_HEADER)

    ip_list = get_list_or(request.json, "banned_ips", str)

    current_app.logger.info(f"{source_ip} requested to add addresses to ban_list: {ip_list}")
    
    result = shared.ban_list.add_all(sent_admin_key, ip_list)

    if result == False:
        current_app.logger.warning(
            f"Failed to add requested addresses ({ip_list}) to ban_list. Invalid admin key ({sent_admin_key}) sent from {source_ip}"
        )
        return jsonify({}), 403
    elif result == None:
        current_app.logger.warning(
            f"Failed to add requested addresses ({ip_list}) to ban_list. Invalid IP address sent from {source_ip}"
        )
        return jsonify({}), 400

    current_app.logger.info(f"Adding addresses to ban_list.")

    return jsonify({"banned_ips": list(map(lambda x: str(x), shared.ban_list.get_all()))}), 200

@api_v1_bp.route("/admin/ban-list", methods=["DELETE"])
def remove_from_ban_list():
    source_ip = get_and_validate_ip()

    sent_admin_key = request.headers.get(shared.ADMIN_KEY_HEADER)

    ip_list = get_list_or(request.json, "banned_ips", str)
    result = shared.ban_list.remove_all(sent_admin_key, ip_list)

    if not result:
        current_app.logger.warning(
            f"Failed to remove requested addresses ({ip_list}) from ban_list. Invalid admin key ({sent_admin_key}) sent from {source_ip}"
        )
        return jsonify({}), 403

    current_app.logger.info(f"Removing addresses from ban_list: {shared.ban_list}")

    return jsonify({"banned_ips": list(map(lambda x: str(x), shared.ban_list.get_all()))}), 200

@api_v1_bp.route("/admin/ban-list", methods=["GET"])
def get_ban_list():
    source_ip = get_and_validate_ip()

    sent_admin_key = request.headers.get(shared.ADMIN_KEY_HEADER)
    if not shared.ban_list.secured_ip_list.validate(sent_admin_key):
        return jsonify({}), 403

    return jsonify({"banned_ips": list(map(lambda x: str(x), shared.ban_list.get_all()))}), 200

@api_v1_bp.route("/admin/verified-list", methods=["PUT"])
def add_to_verified_list():
    source_ip = get_and_validate_ip()

    sent_admin_key = request.headers.get(shared.ADMIN_KEY_HEADER)

    ip_list = get_list_or(request.json, "verified_ips", str)

    current_app.logger.info(f"{source_ip} requested to add addresses to verified_list: {ip_list}")

    result = shared.verified_list.add_all(sent_admin_key, ip_list)

    if result == False:
        current_app.logger.warning(
            f"Failed to add requested addresses ({ip_list}) to verified_list. Invalid admin key ({sent_admin_key}) sent from {source_ip}"
        )
        return jsonify({}), 403
    elif result == None:
        current_app.logger.warning(
            f"Failed to add requested addresses ({ip_list}) to verified_list. Invalid IP address sent from {source_ip}"
        )
        return jsonify({}), 400
    
    current_app.logger.info(f"Adding addresses to verified_list")

    return jsonify({"verified_ips": list(map(lambda x: str(x), shared.verified_list.get_all()))}), 200

@api_v1_bp.route("/admin/verified-list", methods=["DELETE"])
def delete_from_verified_list():
    source_ip = get_and_validate_ip()

    sent_admin_key = request.headers.get(shared.ADMIN_KEY_HEADER)

    ip_list = get_list_or(request.json, "verified_ips", str)
    result = shared.verified_list.remove_all(sent_admin_key, ip_list)

    if not result:
        current_app.logger.warning(
            f"Failed to remove requested addresses ({ip_list}) from verified_list. Invalid admin key ({sent_admin_key}) sent from {source_ip}"
        )
        return jsonify({}), 403

    current_app.logger.info(f"Removing addresses from verified_list: {shared.verified_list}")

    return jsonify({"verified_ips": list(map(lambda x: str(x), shared.verified_list.get_all()))}), 200

@api_v1_bp.route("/admin/verified-list", methods=["GET"])
def get_verified_list():
    source_ip = get_and_validate_ip()

    sent_admin_key = request.headers.get(shared.ADMIN_KEY_HEADER)
    if not shared.ban_list.secured_ip_list.validate(sent_admin_key):
        return jsonify({}), 403

    return jsonify({"verified_ips": list(map(lambda x: str(x), shared.verified_list.get_all()))}), 200


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
        jsonify(
            {"status": "no_key", "message": shared.KEY_HEADER + " header not specified"}
        ),
        400,
    )


@api_v1_bp.errorhandler(InvalidSecretKey)
def handle_invalid_secret_key(e):
    return jsonify({"status": "forbidden"}), 403


@api_v1_bp.errorhandler(Banned)
def handle_banned_user(e):
    return jsonify({"status": "forbidden"}), 403

@api_v1_bp.errorhandler(Exception)
def handle_general_exception(e):
    if shared.DEBUG_MODE:
        return jsonify({
            "status": "error", 
            "message": str(e),
            "stack": traceback.format_exc()
        }), 500
    else:
        return jsonify({
            "status": "error", 
            "message": "An unexpected error occurred."
        }), 500

def update_server(server_id: str, update_server: Callable[[Server], Server]):
    key = get_key()

    existing_server = [x.unique_id for x in shared.server_list.get_all()]

    if server_id not in existing_server:
        current_app.logger.warning(
            f"Update failed. Server with id {server_id} not registered."
        )
        return (
            jsonify({"status": "not_registered", "message": "server not registered"}),
            404,
        )

    server = shared.server_list.update(server_id, key, update_server)

    if server is None:
        current_app.logger.warning(
            f"Update failed. Server with id {server_id} not registered."
        )
        return (
            jsonify({"status": "not_registered", "message": "server not registered"}),
            400,
        )
    timeout = server.last_heartbeat + shared.server_list.heartbeat_timeout

    current_app.logger.info(
        f'Update/Heartbeat received from server "{server.name}" ({server.unique_id}) at {server.ip_address}:{server.ports.game})'
    )

    return jsonify({"refresh_before": timeout, "server": server}), 200
