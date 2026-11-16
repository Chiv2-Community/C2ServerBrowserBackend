"""Generated from OpenAPI. DO NOT EDIT; run uv run server-browser-codegen."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union

from server_browser_models.runtime import WireModel

class GameJoinRedemptionRequest(WireModel):
    ticket: str = Field(alias="ticket", json_schema_extra={"format": "", "nullable": False})
    playfab_id: str = Field(alias="playfab_id", json_schema_extra={"format": "", "nullable": False})
