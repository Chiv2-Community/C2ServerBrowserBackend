"""Application implementation of the generated Chivalry compatibility API."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from ipaddress import ip_address as parse_ip_address
from pathlib import Path
from uuid import uuid4

from server_browser_server.runtime import RequestContext
from server_browser_server.apis.chiv2_compat_api_base import BaseChiv2CompatApi
from server_browser_models.models import (
    MatchmakeRequest, MotdRequest, PlayfabErrorResponse, PlayfabGame,
    PlayfabMatchmakeResponse, TbioMotdResponse, TbioServerListResponse,
)
from server_browser_server.runtime import ApiResponse
from server_browser_backend.models.tbio import server_list_data
from server_browser_backend.routes.shared import Banned, RequestPolicy
from server_browser_backend.server_list import ServerList


class CompatibilityApi(BaseChiv2CompatApi):
    def __init__(self, *, server_list: ServerList, policy: RequestPolicy, motd_directory: Path):
        self.server_list = server_list
        self.policy = policy
        self.motd_directory = motd_directory

    def tbio_get_servers(self, request: RequestContext) -> ApiResponse[TbioServerListResponse]:
        name = None
        client_ip = None
        try:
            client_ip = parse_ip_address(self.policy.get_and_validate_ip(request))
        except Banned:
            name = "This address is banned. Ensure your VPN is disabled."
        data = server_list_data(self.server_list.get_all(), client_ip, name)
        return ApiResponse(TbioServerListResponse(success=True, data=data))

    def get_motd(self, request: RequestContext, motd_request: MotdRequest) -> ApiResponse[TbioMotdResponse]:
        suffix = ""
        try:
            self.policy.get_and_validate_ip(request)
        except Banned:
            suffix = "_banned"
        language = motd_request.language
        if not language.isalnum():
            language = "en"
        location = self.motd_directory / f"{language}{suffix}.json"
        if not location.exists():
            location = self.motd_directory / f"en{suffix}.json"
        data = json.loads(location.read_text())
        expiration = int((datetime.now() + timedelta(days=365)).timestamp())
        return ApiResponse(TbioMotdResponse(success=True, data=data, expiration=expiration))

    def playfab_client_matchmake(self, request: RequestContext, matchmake_request: MatchmakeRequest) -> ApiResponse[PlayfabMatchmakeResponse] | ApiResponse[PlayfabErrorResponse]:
        client_ip = self.policy.get_and_validate_ip(request)
        server = self.server_list.get(matchmake_request.lobby_id)
        if server is None:
            return ApiResponse(PlayfabErrorResponse(
                code=404, data={}, message="Lobby does not exist", params={}, success=False,
            ), 404)
        address = server.address_for(parse_ip_address(client_ip))
        return ApiResponse(PlayfabMatchmakeResponse(
            code=200, status="OK", data=PlayfabGame(
                server_hostname=address, server_ipv4_address=address,
                server_port=server.ports.game, ticket=str(uuid4()),
            ),
        ))
