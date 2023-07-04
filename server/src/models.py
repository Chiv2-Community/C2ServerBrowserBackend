from dataclasses import dataclass
from datetime import datetime
from typing import List

    
@dataclass
class Mod:
    name: str
    organization: str
    version: str

    @staticmethod
    def from_json(json: dict):
        return Mod(
            json['name'],
            json['organization'],
            json['version'],
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
        return Server(
            json['ip_address'],
            json['port'],
            json['last_heartbeat'],
            json['name'],
            json['description'],
            json['current_map'],
            json['player_count'],
            json['max_players'],
            list(map(lambda mod: Mod.from_json(mod), json['mods']))
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
            json['ip_address'],
            json['port'],
            json['current_map'],
            json['player_count'],
            json['max_players'],
        )