from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional

from server_browser_backend.dict_util import get_list_or, get_or, get_or_optional

@dataclass(frozen=True)
class Mod:
    name: str
    organization: str
    version: str

    @staticmethod
    def from_json(json: dict):
        return Mod(
            get_or(json, "name", str),
            get_or(json, "organization", str),
            get_or(json, "version", str),
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
    mods: List[Mod]

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
            self.mods,
        )
    
    def unverified(self) -> Server:
        return Server(
            self.unique_id,
            self.ip_address,
            self.local_ip_address,
            self.ports,
            self.password_protected,
            self.last_heartbeat,
            "Unverified - " + self.name,
            self.description,
            self.current_map,
            self.player_count,
            self.max_players,
            self.mods,
        )
    
    def to_server_response(self) -> dict:
        self_dict = asdict(self)

        del self_dict["ip_address"]
        del self_dict["local_ip_address"]

        return self_dict



@dataclass(frozen=True)
class UpdateRegisteredServer:
    current_map: str
    player_count: int
    max_players: int

    @staticmethod
    def from_json(json: dict):
        return UpdateRegisteredServer(
            get_or(json, "current_map", str),
            get_or(json, "player_count", int),
            get_or(json, "max_players", int),
        )


@dataclass(frozen=True)
class Chivalry2Ports:
    game: int
    ping: int
    a2s: int

    @staticmethod
    def from_json(json: dict):
        return Chivalry2Ports(
            get_or(json, "game", int),
            get_or(json, "ping", int),
            get_or(json, "a2s", int),
        )
