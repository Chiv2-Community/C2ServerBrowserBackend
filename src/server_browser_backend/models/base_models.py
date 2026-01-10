from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional

from server_browser_backend.dict_util import get_list_or, get_or, get_or_optional

@dataclass(frozen=True)
class Mod:
    name: str
    organization: str
    version: str
    active: bool = False

    @staticmethod
    def from_json(json: dict):
        return Mod(
            get_or(json, "name", str),
            get_or(json, "organization", str),
            get_or(json, "version", str),
            get_or(json, "active", bool, default=lambda: False),
        )


@dataclass(frozen=True)
class ServerRegistrationRequest:
    ports: Chivalry2Ports
    password_protected: bool
    name: str
    description: str
    current_map: str
    player_count: int
    max_players: int
    mods: List[Mod]
    local_ip_address: Optional[str]

    @staticmethod
    def from_json(json: dict):
        mod_objs = get_list_or(json, "mods", dict, lambda: [])

        return ServerRegistrationRequest(
            Chivalry2Ports.from_json(get_or(json, "ports", dict)),
            get_or(json, "password_protected", bool, default=lambda: False),
            get_or(json, "name", str),
            get_or(json, "description", str),
            get_or(json, "current_map", str),
            get_or(json, "player_count", int),
            get_or(json, "max_players", int),
            list(map(Mod.from_json, mod_objs)),
            get_or_optional(json, "local_ip_address", str),
        )


@dataclass(frozen=True)
class Server:
    unique_id: str
    ip_address: str
    local_ip_address: Optional[str]
    ports: Chivalry2Ports
    password_protected: bool
    last_heartbeat: float
    name: str
    description: str
    current_map: str
    player_count: int
    max_players: int
    is_verified: bool
    mods: List[Mod]

    @staticmethod
    def create_after_registration(
        registration: ServerRegistrationRequest, unique_id: str, ip_address: str, last_heartbeat: float
    ) -> Server:
        return Server(
            unique_id,
            ip_address,
            registration.local_ip_address,
            registration.ports,
            registration.password_protected,
            last_heartbeat,
            registration.name,
            registration.description,
            registration.current_map,
            registration.player_count,
            registration.max_players,
            False,
            registration.mods,
        )

    @staticmethod
    def from_json(json: dict):
        mod_objs = get_list_or(json, "mods", dict, lambda: [])

        return Server(
            get_or(json, "unique_id", str),
            get_or(json, "ip_address", str),
            get_or_optional(json, "local_ip_address", str),
            Chivalry2Ports.from_json(get_or(json, "ports", dict)),
            get_or(json, "password_protected", bool, default=lambda: False),
            get_or(json, "last_heartbeat", float),
            get_or(json, "name", str),
            get_or(json, "description", str),
            get_or(json, "current_map", str),
            get_or(json, "player_count", int),
            get_or(json, "max_players", int),
            False,
            list(map(Mod.from_json, mod_objs)),
        )

    def with_heartbeat(self, heartbeat_time: float):
        return Server(
            self.unique_id,
            self.ip_address,
            self.local_ip_address,
            self.ports,
            self.password_protected,
            heartbeat_time,
            self.name,
            self.description,
            self.current_map,
            self.player_count,
            self.max_players,
            self.is_verified,
            self.mods,
        )

    def with_update(self, update_request: UpdateRegisteredServer) -> Server:
        return Server(
            self.unique_id,
            self.ip_address,
            self.local_ip_address,
            self.ports,
            self.password_protected,
            self.last_heartbeat,
            self.name,
            self.description,
            update_request.current_map,
            update_request.player_count,
            update_request.max_players,
            self.is_verified,
            update_request.mods,
        )

    def unverified(self) -> Server:
        return Server(
            self.unique_id,
            self.ip_address,
            self.local_ip_address,
            self.ports,
            self.password_protected,
            self.last_heartbeat,
            self.name,
            self.description,
            self.current_map,
            self.player_count,
            self.max_players,
            False,
            self.mods,
        )

    def verified(self) -> Server:
        return Server(
            self.unique_id,
            self.ip_address,
            self.local_ip_address,
            self.ports,
            self.password_protected,
            self.last_heartbeat,
            self.name,
            self.description,
            self.current_map,
            self.player_count,
            self.max_players,
            True,
            self.mods,
        )


@dataclass(frozen=True)
class ServerResponse:
    unique_id: str
    ports: Chivalry2Ports
    password_protected: bool
    last_heartbeat: float
    name: str
    description: str
    current_map: str
    player_count: int
    max_players: int
    is_verified: bool
    mods: List[Mod]

    @staticmethod
    def from_server(server: Server) -> ServerResponse:
        return ServerResponse(
            server.unique_id,
            server.ports,
            server.password_protected,
            server.last_heartbeat,
            server.name,
            server.description,
            server.current_map,
            server.player_count,
            server.max_players,
            server.is_verified,
            server.mods,
        )



@dataclass(frozen=True)
class UpdateRegisteredServer:
    current_map: str
    player_count: int
    max_players: int
    mods: List[Mod]

    @staticmethod
    def from_json(json: dict):
        mod_objs = get_list_or(json, "mods", dict, lambda: [])

        return UpdateRegisteredServer(
            get_or(json, "current_map", str),
            get_or(json, "player_count", int),
            get_or(json, "max_players", int),
            list(map(Mod.from_json, mod_objs)),
        )


@dataclass(frozen=True)
class Chivalry2Ports:
    game: int
    a2s: int
    ping: int

    @staticmethod
    def from_json(json: dict):
        return Chivalry2Ports(
            get_or(json, "game", int),
            get_or(json, "a2s", int),
            get_or(json, "ping", int),
        )


@dataclass(frozen=True)
class BanStatusResponse:
    banned: bool


@dataclass(frozen=True)
class StatusResponse:
    status: str
    message: str
    context: Optional[dict] = None


@dataclass(frozen=True)
class ErrorResponse:
    status: str
    message: str
    stack: Optional[str] = None


@dataclass(frozen=True)
class ServerListResponse:
    servers: List[ServerResponse]


@dataclass(frozen=True)
class BanListResponse:
    banned_ips: List[str]


@dataclass(frozen=True)
class VerifiedListResponse:
    verified_ips: List[str]


@dataclass(frozen=True)
class RegistrationResponse:
    key: str
    refresh_before: float
    server: ServerResponse


@dataclass(frozen=True)
class UpdateResponse:
    refresh_before: float
    server: ServerResponse


@dataclass(frozen=True)
class IpListRequest:
    banned_ips: Optional[List[str]] = None
    verified_ips: Optional[List[str]] = None

    @staticmethod
    def from_json(json: dict):
        return IpListRequest(
            get_or_optional(json, "banned_ips", list),
            get_or_optional(json, "verified_ips", list),
        )
