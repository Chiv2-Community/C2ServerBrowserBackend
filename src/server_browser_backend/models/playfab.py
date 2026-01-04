from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Wrapper:
    code: int
    status: str
    data: Game


@dataclass(frozen=True)
class Game:
    ServerHostname: str
    ServerIPV4Address: str
    ServerPort: int
    Ticket: str


@dataclass(frozen=True)
class Error:
    code: int
    data: dict
    message: str
    params: dict
    success: bool


@dataclass(frozen=True)
class MatchmakeRequest:
    lobby_id: str

    @staticmethod
    def from_json(json: dict):
        from server_browser_backend.dict_util import get_or

        return MatchmakeRequest(get_or(json, "LobbyId", str))
