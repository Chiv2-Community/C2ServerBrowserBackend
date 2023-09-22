from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, List, Optional

from server_browser_backend.dict_util import get_or
from server_browser_backend.models.base_models import Server
from server_browser_backend.type_vars import A


@dataclass(frozen=True)
class Wrapper(Generic[A]):
    Success: bool
    Data: A
    expiration: Optional[int] = None

    @staticmethod
    def from_servers(servers: List[Server]) -> Wrapper[ServerListData]:
        return Wrapper(True, ServerListData.from_servers(servers))


@dataclass(frozen=True)
class ServerListData:
    GameCount: int
    PlayerCount: int
    Games: List[Game]

    @staticmethod
    def from_servers(servers: List[Server], client_ip: str) -> ServerListData:
        return ServerListData(
            len(servers),
            sum(map(lambda s: s.player_count, servers)),
            list(map(lambda s: Game.from_server(s, client_ip), servers)),
        )
    
    def add_game(self, game: Game) -> ServerListData:
        return ServerListData(
            self.GameCount + 1,
            self.PlayerCount + game.MaxPlayers,
            self.Games + [game],
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
    def from_server(server: Server, client_ip: str) -> Game:
        ip_address = server.local_ip_address if client_ip == server.ip_address and server.local_ip_address is not None else server.ip_address
        return Game(
            "paris",
            server.unique_id,
            server.max_players,
            False,
            "dummy",
            "40p",
            [*range(server.player_count)],
            500,
            1,
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
                "true" if server.password_protected else "false",
                "6",
                "277",
            ),
            int(server.last_heartbeat),
            ip_address,
            ip_address,
            server.ports.game,
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
