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
