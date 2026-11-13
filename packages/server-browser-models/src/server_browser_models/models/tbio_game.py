"""Generated from OpenAPI. DO NOT EDIT; run uv run server-browser-codegen."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union
from server_browser_models.models.tbio_tags import TbioTags
from server_browser_models.runtime import LegacyIPAddress

from server_browser_models.runtime import WireModel

class TbioGame(WireModel):
    region: str = Field(alias="Region", json_schema_extra={"format": "", "nullable": False})
    lobby_id: str = Field(alias="LobbyId", json_schema_extra={"format": "", "nullable": False})
    max_players: int = Field(alias="MaxPlayers", json_schema_extra={"format": "", "nullable": False})
    official: bool = Field(alias="Official", json_schema_extra={"format": "", "nullable": False})
    build_version: str = Field(alias="BuildVersion", json_schema_extra={"format": "", "nullable": False})
    game_mode: str = Field(alias="GameMode", json_schema_extra={"format": "", "nullable": False})
    player_user_ids: List[int] = Field(alias="PlayerUserIds", json_schema_extra={"format": "", "nullable": False})
    run_time: int = Field(alias="RunTime", json_schema_extra={"format": "", "nullable": False})
    game_server_state: int = Field(alias="GameServerState", json_schema_extra={"format": "", "nullable": False})
    tags: TbioTags = Field(alias="Tags", json_schema_extra={"format": "", "nullable": False})
    last_heartbeat: int = Field(alias="LastHeartbeat", json_schema_extra={"format": "", "nullable": False})
    server_hostname: LegacyIPAddress = Field(alias="ServerHostname", json_schema_extra={"format": "legacy-ip-address", "nullable": False})
    server_ipv4_address: LegacyIPAddress = Field(alias="ServerIPV4Address", json_schema_extra={"format": "legacy-ip-address", "nullable": False})
    server_port: int = Field(alias="ServerPort", json_schema_extra={"format": "", "nullable": False})
