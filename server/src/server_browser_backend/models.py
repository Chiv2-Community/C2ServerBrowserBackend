from dataclasses import dataclass
from datetime import datetime
from .dict_util import get_or
from typing import List, Dict, Callable, TypeVar, Type
    
@dataclass
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

@dataclass
class Server:
    ip_address: str
    port: int
    last_heartbeat: float
    name: str
    description: str
    current_map: str
    player_count: int
    max_players: int
    mods: List[Mod]

    def id(self):
        return (self.ip_address, self.port)

    @staticmethod
    def from_json(json: dict):
        mods_json_list = get_or(json, 'mods', List[any], lambda k: [])
        mods = list(map(lambda mod: Mod.from_json(mod), mods_json_list))

        return Server(
            get_or(json, 'ip_address', str),
            get_or(json, 'port', int),
            get_or(json, 'last_heartbeat', float),
            get_or(json, 'name', str),
            get_or(json, 'description', str),
            get_or(json, 'current_map', str),
            get_or(json, 'player_count', int),
            get_or(json, 'max_players', int),
            mods
        )

@dataclass
class HeartbeatSignal:
    ip_address: str
    port: int
    current_map: str
    player_count: int
    max_players: int

    @staticmethod
    def from_json(json: dict):
        return HeartbeatSignal(
            get_or(json, 'ip_address', str),
            get_or(json, 'port', int),
            get_or(json, 'current_map', str),
            get_or(json, 'player_count', int),
            get_or(json, 'max_players', int),
        )
