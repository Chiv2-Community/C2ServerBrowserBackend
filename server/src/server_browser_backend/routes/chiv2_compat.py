from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta
from os import path
from typing import Callable, Dict, List, Optional, Tuple, TypeVar
from uuid import uuid4

from flask import (Blueprint, Flask, Request, jsonify, request, send_file,
                   send_from_directory)

from server_browser_backend import dict_util, playfab, tbio
from server_browser_backend.dict_util import DictKeyError, DictTypeError
from server_browser_backend.models import Server, UpdateRegisteredServer
from server_browser_backend.routes.shared import (get_and_validate_ip,
                                                  server_list)
from server_browser_backend.server_list import (InvalidSecretKey,
                                                SecretKeyMissing, ServerList)

tbio_bp = Blueprint("chiv2_compat_tbio", __name__, url_prefix="/api/tbio")


@tbio_bp.route("/GetCurrentGames", methods=["POST"])
def tbio_get_servers():
    get_and_validate_ip()  # Check if banned
    servers = tbio.ServerListData.from_servers(server_list.get_all())
    return jsonify(tbio.Wrapper(True, servers)), 200


@tbio_bp.route("/GetMotd", methods=["POST"])
def get_motd():
    get_and_validate_ip()
    language = dict_util.get_or(request.json, "Language", str, lambda: "en")

    language_path = f"assets/motd/{language}.json"
    default_path = f"assets/motd/en.json"

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
    get_and_validate_ip()
    server_id = request.json.get("LobbyId")
    if not server_id:
        return jsonify(playfab.Error(400, {}, "No LobbyId provided.", {}, False)), 400

    server = server_list.get(server_id)

    if not server:
        return jsonify(playfab.Error(404, {}, "Lobby does not exist", {}, False)), 404

    return (
        jsonify(
            playfab.Wrapper(
                200,
                "OK",
                playfab.Game(
                    server.ip_address,
                    server.ip_address,
                    server.ports.game,
                    str(uuid4()),
                ),
            )
        ),
        200,
    )
