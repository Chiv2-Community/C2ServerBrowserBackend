"""Domain state and conversions to the generated API contract."""
from __future__ import annotations

from dataclasses import dataclass, replace
from ipaddress import IPv4Address, IPv6Address
from typing import Any

from server_browser_api.models import (
    Chivalry2Ports, Mod, ServerListResponse, ServerRegistrationRequest,
    ServerResponse, ServerResponseWithIP, UpdateRegisteredServer,
)
from server_browser_backend.dict_util import decode_ip_address, get_or


@dataclass(frozen=True)
class Server:
    unique_id: str
    ip_address: IPv4Address | IPv6Address
    local_ip_address: IPv4Address | IPv6Address | None
    ports: Chivalry2Ports
    password_protected: bool
    last_heartbeat: float
    name: str
    description: str
    current_map: str
    player_count: int
    max_players: int
    is_verified: bool
    mods: list[Mod]

    @staticmethod
    def create_after_registration(
        registration: ServerRegistrationRequest, unique_id: str, ip_address: str,
        last_heartbeat: float,
    ) -> Server:
        return Server(
            unique_id=unique_id,
            ip_address=decode_ip_address(ip_address).value,
            local_ip_address=registration.local_ip_address,
            ports=registration.ports,
            password_protected=registration.password_protected,
            last_heartbeat=last_heartbeat,
            name=registration.name,
            description=registration.description,
            current_map=registration.current_map,
            player_count=registration.player_count,
            max_players=registration.max_players,
            is_verified=False,
            mods=registration.mods,
        )

    @staticmethod
    def from_json(value: dict[str, Any]) -> Server:
        return Server.create_after_registration(
            ServerRegistrationRequest.from_json(value),
            get_or(value, "unique_id", str),
            get_or(value, "ip_address", str),
            get_or(value, "last_heartbeat", float),
        )

    def with_heartbeat(self, heartbeat_time: float) -> Server:
        return replace(self, last_heartbeat=heartbeat_time)

    def with_update(self, update_request: UpdateRegisteredServer) -> Server:
        return replace(
            self, current_map=update_request.current_map,
            player_count=update_request.player_count, max_players=update_request.max_players,
            mods=update_request.mods if update_request.mods is not None else self.mods,
        )

    def unverified(self) -> Server:
        return replace(self, is_verified=False)

    def verified(self) -> Server:
        return replace(self, is_verified=True)


def server_response(server: Server) -> ServerResponse:
    return ServerResponse(
        unique_id=server.unique_id, ports=server.ports,
        password_protected=server.password_protected, last_heartbeat=server.last_heartbeat,
        name=server.name, description=server.description, current_map=server.current_map,
        player_count=server.player_count, max_players=server.max_players,
        is_verified=server.is_verified, mods=server.mods,
    )


def server_response_with_ip(server: Server) -> ServerResponseWithIP:
    return ServerResponseWithIP(
        **server_response(server).model_dump(), ip_address=server.ip_address,
        local_ip_address=server.local_ip_address,
    )


def server_listing(servers: list[Server], include_ip: bool) -> ServerListResponse:
    return ServerListResponse(servers=[
        server_response_with_ip(server) if include_ip else server_response(server)
        for server in servers
    ])
