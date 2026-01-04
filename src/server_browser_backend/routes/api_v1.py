from __future__ import annotations

from datetime import datetime
from typing import Callable
from uuid import uuid4

from dataclasses import asdict
from flask import Blueprint, current_app, jsonify, request, send_file

from server_browser_backend.dict_util import DictKeyError, DictTypeError
from server_browser_backend.models.base_models import (
    BanListResponse,
    BanStatusResponse,
    ErrorResponse,
    IpListRequest,
    RegistrationResponse,
    Server,
    ServerListResponse,
    ServerRegistrationRequest,
    ServerResponse,
    StatusResponse,
    UpdateRegisteredServer,
    UpdateResponse,
    VerifiedListResponse,
)
from server_browser_backend.routes import shared
from server_browser_backend.routes.shared import Banned, JsonMissing, get_and_validate_ip, get_json, get_key
from server_browser_backend.server_list import InvalidSecretKey, SecretKeyMissing

import traceback

api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


@api_v1_bp.route("/swagger.yaml")
def send_swagger():
    get_and_validate_ip()
    return send_file("../../assets/chiv2-server-browser-api.yaml")

@api_v1_bp.route("/check-banned/<ip>", methods=["GET"])
def check_banned(ip: str):
    get_and_validate_ip()
    return jsonify(BanStatusResponse(shared.ban_list.contains(ip))), 200

@api_v1_bp.route("/servers", methods=["POST"])
def register():
    server_ip = get_and_validate_ip()

    registration = ServerRegistrationRequest.from_json(get_json())
    server = Server.create_after_registration(
        registration, str(uuid4()), server_ip, datetime.now().timestamp()
    )

    if shared.is_whitelisted():
        server = server.verified()
    else:
        server = server.unverified()

    key = shared.server_list.register(server)
    timeout = server.last_heartbeat + shared.server_list.heartbeat_timeout

    current_app.logger.info(
        f'Registered server "{server.name}" at {server.ip_address}:{server.ports.game}'
    )

    return (
        jsonify(
            RegistrationResponse(
                key,
                timeout,
                ServerResponse.from_server(server),
            )
        ),
        201,
    )


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
    update_request = UpdateRegisteredServer.from_json(get_json())

    return update_server(
        server_id,
        lambda server: server.with_update(update_request),
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
            jsonify(StatusResponse("not_registered", "server not registered")),
            404,
        )

    current_app.logger.info(
        f'Deleted server with id "{server.name}" at {server.ip_address}:{server.ports.game}'
    )
    return (
        jsonify(StatusResponse("deleted", "The server has been deleted")),
        200,
    )


@api_v1_bp.route("/servers", methods=["GET"])
def get_servers():
    get_and_validate_ip()
    servers = shared.server_list.get_all()
    server_listing_servers = [ServerResponse.from_server(x) for x in servers]
    return jsonify(ServerListResponse(server_listing_servers)), 200


@api_v1_bp.route("/admin/ban-list", methods=["PUT"])
def add_to_ban_list():
    source_ip = get_and_validate_ip()

    sent_admin_key = request.headers.get(shared.ADMIN_KEY_HEADER)

    request_model = IpListRequest.from_json(get_json())
    ip_list = request_model.banned_ips

    if ip_list is None:
        return jsonify(StatusResponse("invalid_request", "banned_ips is required")), 400

    truncated_ip_list_string = ", ".join(ip_list[:10])
    if len(ip_list) > 10:
        truncated_ip_list_string += f" (and {len(ip_list) - 10} more)"

    current_app.logger.info(f"{source_ip} requested to add addresses to ban_list: {truncated_ip_list_string}")
    
    # Validate the admin key
    if not shared.ban_list.validate(sent_admin_key):
        current_app.logger.warning(
            f"Failed to add requested addresses to ban_list. Invalid admin key sent from {source_ip}"
        )
        return jsonify(StatusResponse("forbidden", "Invalid admin key")), 403

    result = shared.ban_list.add_all(sent_admin_key, ip_list)

    if result is None:
        current_app.logger.warning(
            f"Failed to add requested addresses to ban_list. Invalid IP address sent from {source_ip}"
        )
        return jsonify(StatusResponse("invalid_ip", "Invalid IP address")), 400

    current_app.logger.info(f"Adding addresses to ban_list.")

    return jsonify(BanListResponse(list(map(lambda x: str(x), shared.ban_list.get_all(sent_admin_key))))), 200

@api_v1_bp.route("/admin/ban-list", methods=["DELETE"])
def remove_from_ban_list():
    source_ip = get_and_validate_ip()

    sent_admin_key = request.headers.get(shared.ADMIN_KEY_HEADER)

    request_model = IpListRequest.from_json(get_json())
    ip_list = request_model.banned_ips

    if ip_list is None:
        return jsonify(StatusResponse("invalid_request", "banned_ips is required")), 400

    result = shared.ban_list.remove_all(sent_admin_key, ip_list)

    if not result:
        truncated_ip_list_string = ", ".join(ip_list[:10])
        if len(ip_list) > 10:
            truncated_ip_list_string += f" (and {len(ip_list) - 10} more)"

        current_app.logger.warning(
            f"Failed to remove requested addresses ({truncated_ip_list_string}) from ban_list. Invalid admin key sent from {source_ip}"
        )
        return jsonify(StatusResponse("forbidden", "Invalid admin key")), 403

    current_app.logger.info(f"Removing addresses from ban_list: {shared.ban_list}")

    return jsonify(BanListResponse(list(map(lambda x: str(x), shared.ban_list.get_all(sent_admin_key))))), 200

@api_v1_bp.route("/admin/ban-list", methods=["GET"])
def get_ban_list():
    source_ip = get_and_validate_ip()

    sent_admin_key = request.headers.get(shared.ADMIN_KEY_HEADER)
    if not shared.ban_list.secured_ip_list.validate(sent_admin_key):
        return jsonify(StatusResponse("forbidden", "Invalid admin key")), 403

    return jsonify(BanListResponse(list(map(lambda x: str(x), shared.ban_list.get_all(sent_admin_key))))), 200

@api_v1_bp.route("/admin/verified-list", methods=["PUT"])
def add_to_verified_list():
    source_ip = get_and_validate_ip()

    sent_admin_key = request.headers.get(shared.ADMIN_KEY_HEADER)

    request_model = IpListRequest.from_json(get_json())
    ip_list = request_model.verified_ips

    if ip_list is None:
        return jsonify(StatusResponse("invalid_request", "verified_ips is required")), 400

    truncated_ip_list_string = ", ".join(ip_list[:10])
    if len(ip_list) > 10:
        truncated_ip_list_string += f" (and {len(ip_list) - 10} more)"


    current_app.logger.info(f"{source_ip} requested to add addresses to verified_list: {truncated_ip_list_string}")
    
    # Validate the admin key
    if not shared.verified_list.validate(sent_admin_key):
        current_app.logger.warning(
            f"Failed to add requested addresses to verified_list. Invalid admin key sent from {source_ip}"
        )
        return jsonify(StatusResponse("forbidden", "Invalid admin key")), 403

    result = shared.verified_list.add_all(sent_admin_key, ip_list)

    if result is None:
        current_app.logger.warning(
            f"Failed to add requested addresses to verified_list. Invalid IP address sent from {source_ip}"
        )
        return jsonify(StatusResponse("invalid_ip", "Invalid IP address")), 400
    
    current_app.logger.info(f"Adding addresses to verified_list")

    return jsonify(VerifiedListResponse(list(map(lambda x: str(x), shared.verified_list.get_all(sent_admin_key))))), 200

@api_v1_bp.route("/admin/verified-list", methods=["DELETE"])
def delete_from_verified_list():
    source_ip = get_and_validate_ip()

    sent_admin_key = request.headers.get(shared.ADMIN_KEY_HEADER)

    request_model = IpListRequest.from_json(get_json())
    ip_list = request_model.verified_ips

    if ip_list is None:
        return jsonify(StatusResponse("invalid_request", "verified_ips is required")), 400

    result = shared.verified_list.remove_all(sent_admin_key, ip_list)

    if not result:
        truncated_ip_list_string = ", ".join(ip_list[:10])
        if len(ip_list) > 10:
            truncated_ip_list_string += f" (and {len(ip_list) - 10} more)"

        current_app.logger.warning(
            f"Failed to remove requested addresses ({truncated_ip_list_string}) from verified_list. Invalid admin key sent from {source_ip}"
        )
        return jsonify(StatusResponse("forbidden", "Invalid admin key")), 403

    current_app.logger.info(f"Removing addresses from verified_list: {shared.verified_list}")

    return jsonify(VerifiedListResponse(list(map(lambda x: str(x), shared.verified_list.get_all(sent_admin_key))))), 200

@api_v1_bp.route("/admin/verified-list", methods=["GET"])
def get_verified_list():
    source_ip = get_and_validate_ip()

    sent_admin_key = request.headers.get(shared.ADMIN_KEY_HEADER)
    if not shared.verified_list.validate(sent_admin_key):
        current_app.logger.warning(f"Invalid admin key sent from {source_ip}")
        return jsonify(StatusResponse("forbidden", "Invalid admin key")), 403

    return jsonify(VerifiedListResponse(list(map(lambda x: str(x), shared.verified_list.get_all(sent_admin_key))))), 200


@api_v1_bp.errorhandler(JsonMissing)
def handle_json_missing(e):
    return (
        jsonify(
            StatusResponse(
                "missing_json_body",
                "JSON body is required",
            )
        ),
        400,
    )


@api_v1_bp.errorhandler(DictKeyError)
def handle_dict_key_error(e):
    return (
        jsonify(
            StatusResponse(
                "invalid_json_body",
                f"Missing key '{e.key}'",
                e.context,
            )
        ),
        400,
    )


@api_v1_bp.errorhandler(DictTypeError)
def handle_dict_type_error(e):
    error_string = f"Invalid type for key '{e.key}'. Got '{e.actual_type.__name__}' with value '{e.value}', but expected '{e.expected_type.__name__}'"
    return (
        jsonify(
            StatusResponse(
                "invalid_json_body",
                error_string,
                e.context,
            )
        ),
        400,
    )


@api_v1_bp.errorhandler(SecretKeyMissing)
def handle_secret_key_missing(e):
    return (
        jsonify(
            StatusResponse("no_key", shared.KEY_HEADER + " header not specified")
        ),
        400,
    )


@api_v1_bp.errorhandler(InvalidSecretKey)
def handle_invalid_secret_key(e):
    return jsonify(StatusResponse("forbidden", "Invalid secret key")), 403


@api_v1_bp.errorhandler(Banned)
def handle_banned_user(e):
    return jsonify(StatusResponse("forbidden", "You are banned")), 403

@api_v1_bp.errorhandler(Exception)
def handle_general_exception(e):
    current_app.logger.error(f"Unhandled exception: {e}", exc_info=True)
    if shared.DEBUG_MODE:
        return jsonify(
            ErrorResponse(
                "error", 
                str(e),
                traceback.format_exc()
            )
        ), 500
    else:
        return jsonify(
            StatusResponse(
                "error", 
                "An unexpected error occurred."
            )
        ), 500

def update_server(server_id: str, update_server: Callable[[Server], Server]):
    key = get_key()

    existing_server = [x.unique_id for x in shared.server_list.get_all()]

    if server_id not in existing_server:
        current_app.logger.warning(
            f"Update failed. Server with id {server_id} not registered."
        )
        return (
            jsonify(StatusResponse("not_registered", "server not registered")),
            404,
        )

    server = shared.server_list.update(server_id, key, update_server)

    if server is None:
        current_app.logger.warning(
            f"Update failed. Server with id {server_id} not registered."
        )
        return (
            jsonify(StatusResponse("not_registered", "server not registered")),
            400,
        )
    timeout = server.last_heartbeat + shared.server_list.heartbeat_timeout

    current_app.logger.info(
        f'Update/Heartbeat received from server "{server.name}" ({server.unique_id}) at {server.ip_address}:{server.ports.game})'
    )

    return jsonify(
        UpdateResponse(timeout, ServerResponse.from_server(server))
    ), 200
