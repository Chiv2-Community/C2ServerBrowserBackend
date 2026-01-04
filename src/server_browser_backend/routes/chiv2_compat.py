from __future__ import annotations

import json
from datetime import datetime, timedelta
from os import path
from uuid import uuid4

from flask import Blueprint, jsonify, request

from server_browser_backend import dict_util
from server_browser_backend.models import playfab, tbio, base_models
from server_browser_backend.routes import shared
from server_browser_backend.routes.shared import get_and_validate_ip, get_json, JsonMissing

tbio_bp = Blueprint("chiv2_compat_tbio", __name__, url_prefix="/api/tbio")

@tbio_bp.route("/GetCurrentGames", methods=["POST"])
def tbio_get_servers():
    banned = False
    client_ip = None
    try:
        client_ip = get_and_validate_ip()
    except shared.Banned:
        banned = True

    fixed_name = "This address is banned. Ensure your VPN is disabled." if banned else None
    servers = tbio.ServerListData.from_servers(shared.server_list.get_all(), client_ip, fixed_name)

    return jsonify(tbio.Wrapper(True, servers)), 200


@tbio_bp.route("/GetMotd", methods=["POST"])
def get_motd():
    banned_suffix = ""
    try:
        get_and_validate_ip()
    except shared.Banned:
        banned_suffix = "_banned"

    motd_request = tbio.MotdRequest.from_json(get_json())
    language = motd_request.language

    language_path = f"assets/motd/{language}{banned_suffix}.json"
    default_path = f"assets/motd/en{banned_suffix}.json"

    motd_path = language_path if path.exists(language_path) else default_path

    with open(motd_path, "r") as f:
        motd = json.load(f)
        one_year_from_now = datetime.now() + timedelta(days=365)
        return (
            jsonify(tbio.Wrapper(True, motd, int(one_year_from_now.timestamp()))),
            200,
        )


playfab_bp = Blueprint("chiv2_compat_playfab", __name__, url_prefix="/api/playfab")


@playfab_bp.route("/Client/Matchmake", methods=["POST"])
def payfab_client_matchmake():
    client_ip = get_and_validate_ip()
    matchmake_request = playfab.MatchmakeRequest.from_json(get_json())
    server_id = matchmake_request.lobby_id
    
    server = shared.server_list.get(server_id)

    if not server:
        return jsonify(playfab.Error(404, {}, "Lobby does not exist", {}, False)), 404

    joining_locally = client_ip == server.ip_address
    has_local_ip = server.local_ip_address is not None

    ip_address = server.local_ip_address if joining_locally and has_local_ip else server.ip_address
    return (
        jsonify(
            playfab.Wrapper(
                200,
                "OK",
                playfab.Game(
                    ip_address,
                    ip_address,
                    server.ports.game,
                    str(uuid4()),
                ),
            )
        ),
        200,
    )

@tbio_bp.errorhandler(JsonMissing)
@playfab_bp.errorhandler(JsonMissing)
def handle_json_missing(e):
    return (
        jsonify(
            base_models.StatusResponse(
                "missing_json_body",
                "JSON body is required",
            )
        ),
        400,
    )

@tbio_bp.errorhandler(Exception)
@playfab_bp.errorhandler(Exception)
def handle_general_exception(e):
    raise e
