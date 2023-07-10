from __future__ import annotations
from dataclasses import dataclass
from typing import List

from server_browser_backend.dict_util import get_or
from server_browser_backend.models import Server

@dataclass(frozen=True)
class Wrapper:
    Success: bool
    Data: ServerListData

    @staticmethod
    def from_servers(servers: List[Server]):
        return Wrapper(True, ServerListData.from_servers(servers))



@dataclass(frozen=True)
class ServerListData:
    GameCount: int
    PlayerCount: int
    Games: List[Game]

    @staticmethod
    def from_servers(servers: List[Server]):
        return ServerListData(
            len(servers),
            sum(map(lambda s: s.player_count, servers)),
            list(map(lambda s: Game.from_server(s), servers))
        )

@dataclass(frozen=True)
class Game:
    Region: str
    LobbyId: str
    MaxPlayers: int
    Official: bool
    BuildVersion: str
    GameMode: str
    PlayerUserIds: List[str]
    RunTime: int
    GameServerState: int
    Tags: Tags
    LastHeartbeat: int
    ServerHostname: str
    ServerIPV4Address: str
    ServerPort: int

    @staticmethod
    def from_server(server: Server):
        return Game(
            "paris",
            server.unique_id,
            server.max_players,
            False,
            "dummy",
            "40p",
            [],
            500,
            0,
            Tags(
                "dummy",
                server.name,
                "paris",
                "true",
                "any",
                "true",
                "2",
                server.current_map,
                str(server.ports.ping),
                str(server.ports.a2s), 
                "0",
                "false",
                "6",
                "277"
            ),
            int(server.last_heartbeat),
            server.ip_address,
            server.ip_address,
            server.ports.game
        )


@dataclass(frozen=True)
class Tags:
    BuildId_s: str
    ServerName_s: str
    Region_s: str
    OFFICIAL_b: str
    Platform_s: str
    FFA_b: str
    MS_i: str
    MapName_s: str
    PingPort_i: str
    QueryPort_i: str
    T0_c: str
    pp_b: str
    t1_c: str
    MTIM_i: str