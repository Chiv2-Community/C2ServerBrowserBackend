"""Generated from OpenAPI. DO NOT EDIT; run scripts/generate_api.py."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union
from server_browser_api.models.tbio_game import TbioGame

from server_browser_api.runtime import WireModel

class TbioServerListData(WireModel):
    game_count: int = Field(alias="GameCount", json_schema_extra={"format": "", "nullable": False})
    player_count: int = Field(alias="PlayerCount", json_schema_extra={"format": "", "nullable": False})
    games: List[TbioGame] = Field(alias="Games", json_schema_extra={"format": "", "nullable": False})
