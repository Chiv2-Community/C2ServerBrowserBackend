"""Generated from OpenAPI. DO NOT EDIT; run uv run server-browser-codegen."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union
from server_browser_models.models.mod import Mod

from server_browser_models.runtime import WireModel

class UpdateRegisteredServer(WireModel):
    player_count: int = Field(alias="player_count", json_schema_extra={"format": "int32", "nullable": False})
    max_players: int = Field(alias="max_players", json_schema_extra={"format": "int32", "nullable": False})
    current_map: str = Field(alias="current_map", json_schema_extra={"format": "", "nullable": False})
    mods: List[Mod] | None = Field(default=None, alias="mods", json_schema_extra={"format": "", "nullable": False})
