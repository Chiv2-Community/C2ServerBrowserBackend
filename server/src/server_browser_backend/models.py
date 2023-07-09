from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from server_browser_backend.dict_util import get_or
from typing import List, Dict, Callable, TypeVar, Type, Any, cast, Optional, Generic
from abc import ABC, abstractmethod

A = TypeVar('A')

@dataclass(frozen=True)
class SecuredResource(Generic[A]):
    """A secured resource can be fetched with no key, but can only be updated with the proper key."""
    key: str
    resource: A

    def get(self) -> A:
        return self.resource

    def validate(self, key: str) -> bool:
        return self.key == key

    def update(self, key: str, update_func: Callable[[A], Optional[A]]) -> Optional[SecuredResource[A]]:
        if self.validate(key):
            update_result = update_func(self.resource)
            if update_result is None:
                return None

            return SecuredResource(key, update_result)
        
        return None
    
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
class UniqueServer(ABC):
    unique_id: str
    ip_address: str
    port: int

@dataclass(frozen=True)
class Server(UniqueServer):
    unique_id: str
    ip_address: str
    port: int
    last_heartbeat: float
    name: str
    description: str
    current_map: str
    player_count: int
    max_players: int
    mods: List[Mod]

    def is_same_server(self, other: UniqueServer):
        self_validation_params = (self.unique_id, self.ip_address, self.port) 
        update_validation_params = (other.unique_id, other.ip_address, other.port) 
        return self_validation_params == update_validation_params


    def with_heartbeat(self, heartbeat: Heartbeat, heartbeat_time: float):
        if not self.is_same_server(heartbeat):
            return None 
        
        return Server(
            self.unique_id,
            self.ip_address,
            self.port,
            heartbeat_time,
            self.name,
            self.description,
            self.current_map,
            self.player_count,
            self.max_players,
            self.mods
        )

    def with_update(self, update_request: UpdateRegisteredServer) -> Optional[Server]:
        if not self.is_same_server(update_request):
            return None 

        return Server(
            self.unique_id,
            self.ip_address,
            self.port,
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
        mods_json_list: List[Any] = get_or(json, 'mods', List, lambda: [])
        
        # Iterate over the mods and make sure they are all dicts
        for mod in mods_json_list:
            if not isinstance(mod, Dict):
                raise TypeError(f"Mod {str(mod)} is not a dict")

        safer_mods_json_list: List[Dict[Any, Any]] = cast(List[Dict[Any, Any]], mods_json_list)

        mods = list(map(lambda mod: Mod.from_json(mod), safer_mods_json_list))

        return Server(
            get_or(json, 'unique_id', str),
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

@dataclass(frozen=True)
class Heartbeat(UniqueServer):
    unique_id: str
    ip_address: str
    port: int
    
    @staticmethod
    def from_json(json: dict):
        return Heartbeat(
            get_or(json, 'unique_id', str),
            get_or(json, 'ip_address', str),
            get_or(json, 'port', int)
        )


@dataclass(frozen=True)
class UpdateRegisteredServer(UniqueServer):
    unique_id: str
    ip_address: str
    port: int
    current_map: str
    player_count: int
    max_players: int

    @staticmethod
    def from_json(json: dict):
        return UpdateRegisteredServer(
            get_or(json, 'unique_id', str),
            get_or(json, 'ip_address', str),
            get_or(json, 'port', int),
            get_or(json, 'current_map', str),
            get_or(json, 'player_count', int),
            get_or(json, 'max_players', int),
        )
