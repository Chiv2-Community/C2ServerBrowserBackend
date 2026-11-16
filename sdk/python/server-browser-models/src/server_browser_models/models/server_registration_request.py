"""Generated from OpenAPI. DO NOT EDIT; run uv run server-browser-codegen."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union
from server_browser_models.models.chivalry2_ports import Chivalry2Ports
from server_browser_models.models.mod import Mod
from server_browser_models.runtime import IPAddress

from server_browser_models.runtime import WireModel

class ServerRegistrationRequest(WireModel):
    ports: Chivalry2Ports = Field(alias="ports", json_schema_extra={"format": "", "nullable": False})
    name: str = Field(alias="name", json_schema_extra={"format": "", "nullable": False})
    description: str = Field(alias="description", json_schema_extra={"format": "", "nullable": False})
    current_map: str = Field(alias="current_map", json_schema_extra={"format": "", "nullable": False})
    player_count: int = Field(alias="player_count", json_schema_extra={"format": "int32", "nullable": False})
    max_players: int = Field(alias="max_players", json_schema_extra={"format": "int32", "nullable": False})
    password_protected: bool = Field(default=False, alias="password_protected", json_schema_extra={"format": "", "nullable": False})
    mods: List[Mod] = Field(default=[], alias="mods", json_schema_extra={"format": "", "nullable": False})
    local_ip_address: IPAddress | None = Field(default=None, alias="local_ip_address", json_schema_extra={"format": "ip-address", "nullable": False})
