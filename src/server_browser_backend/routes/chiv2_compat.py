"""Application implementation of the generated Chivalry compatibility API."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from ipaddress import ip_address as parse_ip_address
from pathlib import Path
from uuid import uuid4

from fastapi import Request
from server_browser_api.apis.chiv2_compat_api_base import BaseChiv2CompatApi
from server_browser_api.apis.chiv2_compat_api import create_router
from server_browser_api.models import (
    MatchmakeRequest, MotdRequest, PlayfabErrorResponse, PlayfabGame,
    PlayfabMatchmakeResponse, TbioMotdResponse, TbioServerListResponse,
)
from server_browser_api.runtime import ApiResponse
from server_browser_backend.models.tbio import server_list_data
from server_browser_backend.routes import shared


class CompatibilityApi(BaseChiv2CompatApi):
    def tbio_get_servers(self, request: Request) -> ApiResponse[TbioServerListResponse]:
        name = None
        client_ip = None
        try:
            client_ip = parse_ip_address(shared.get_and_validate_ip(request))
        except shared.Banned:
            name = "This address is banned. Ensure your VPN is disabled."
        data = server_list_data(shared.server_list.get_all(), client_ip, name)
        return ApiResponse(TbioServerListResponse(success=True, data=data))

    def get_motd(self, request: Request, motd_request: MotdRequest) -> ApiResponse[TbioMotdResponse]:
        suffix = ""
        try:
            shared.get_and_validate_ip(request)
        except shared.Banned:
            suffix = "_banned"
        language = motd_request.language
        if not language.isalnum():
            language = "en"
        directory = Path(__file__).resolve().parents[1] / "assets/motd"
        if not directory.exists():
            directory = Path(__file__).resolve().parents[3] / "assets/motd"
        location = directory / f"{language}{suffix}.json"
        if not location.exists():
            location = directory / f"en{suffix}.json"
        data = json.loads(location.read_text())
        expiration = int((datetime.now() + timedelta(days=365)).timestamp())
        return ApiResponse(TbioMotdResponse(success=True, data=data, expiration=expiration))

    def playfab_client_matchmake(self, request: Request, matchmake_request: MatchmakeRequest) -> ApiResponse[PlayfabMatchmakeResponse] | ApiResponse[PlayfabErrorResponse]:
        client_ip = shared.get_and_validate_ip(request)
        server = shared.server_list.get(matchmake_request.lobby_id)
        if server is None:
            return ApiResponse(PlayfabErrorResponse(
                code=404, data={}, message="Lobby does not exist", params={}, success=False,
            ), 404)
        address = server.local_ip_address if parse_ip_address(client_ip) == server.ip_address and server.local_ip_address is not None else server.ip_address
        return ApiResponse(PlayfabMatchmakeResponse(
            code=200, status="OK", data=PlayfabGame(
                server_hostname=address, server_ipv4_address=address,
                server_port=server.ports.game, ticket=str(uuid4()),
            ),
        ))


compat_router = create_router(CompatibilityApi())
