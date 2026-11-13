"""Generated from OpenAPI. DO NOT EDIT; run uv run server-browser-codegen."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union
from server_browser_models.models.playfab_game import PlayfabGame

from server_browser_models.runtime import WireModel

class PlayfabMatchmakeResponse(WireModel):
    code: int = Field(alias="code", json_schema_extra={"format": "", "nullable": False})
    status: str = Field(alias="status", json_schema_extra={"format": "", "nullable": False})
    data: PlayfabGame = Field(alias="data", json_schema_extra={"format": "", "nullable": False})
