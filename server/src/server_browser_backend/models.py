from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from server_browser_backend.dict_util import get_list_or, get_or
from typing import List, Dict, Callable, TypeVar, Type, Any, cast, Optional, Generic
from abc import ABC, abstractmethod

A = TypeVar('A')

@dataclass(frozen=True)
class Mod:
    name: str
    organization: str
    version: str

    @staticmethod
    def from_json(json: dict):
        return Mod(
            get_or(json, 'name', str),
            get_or(json, 'organization', str),
            get_or(json, 'version', str)
        )

@dataclass(frozen=True)
class Server:
    unique_id: str
    ip_address: str
    ports: Chivalry2Ports
    last_heartbeat: float
    name: str
    description: str
    current_map: str
    player_count: int
    max_players: int
    mods: List[Mod]

    def with_heartbeat(self, heartbeat_time: float):
        return Server(
            self.unique_id,
            self.ip_address,
            self.ports,
            heartbeat_time,
            self.name,
            self.description,
            self.current_map,
            self.player_count,
            self.max_players,
            self.mods
        )

    def with_update(self, update_request: UpdateRegisteredServer) -> Server:
        return Server(
            self.unique_id,
            self.ip_address,
            self.ports,
            self.last_heartbeat,
            self.name,
            self.description,
            update_request.current_map,
            update_request.player_count,
            update_request.max_players,
            self.mods
        )

    @staticmethod
    def from_json(json: dict):
        mod_objs = get_list_or(json, 'mods', dict, lambda: [])
        mods = list(map(Mod.from_json, mod_objs))


        ports_obj = get_or(json, 'ports', dict)
        ports = Chivalry2Ports.from_json(ports_obj)

        return Server(
            get_or(json, 'unique_id', str),
            get_or(json, 'ip_address', str),
            ports,
            get_or(json, 'last_heartbeat', float),
            get_or(json, 'name', str),
            get_or(json, 'description', str),
            get_or(json, 'current_map', str),
            get_or(json, 'player_count', int),
            get_or(json, 'max_players', int),
            mods
        )


@dataclass(frozen=True)
class UpdateRegisteredServer:
    unique_id: str
    current_map: str
    player_count: int
    max_players: int

    @staticmethod
    def from_json(json: dict):
        return UpdateRegisteredServer(
            get_or(json, 'unique_id', str),
            get_or(json, 'current_map', str),
            get_or(json, 'player_count', int),
            get_or(json, 'max_players', int),
        )

@dataclass(frozen=True)
class Chivalry2Ports:
    game: int
    ping: int
    a2s: int

    @staticmethod
    def from_json(json: dict):
        return Chivalry2Ports(
            get_or(json, 'game', int),
            get_or(json, 'ping', int),
            get_or(json, 'a2s', int)
        )