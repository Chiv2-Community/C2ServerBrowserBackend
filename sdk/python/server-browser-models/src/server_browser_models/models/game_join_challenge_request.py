"""Generated from OpenAPI. DO NOT EDIT; run uv run server-browser-codegen."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union
from server_browser_models.runtime import IPAddress

from server_browser_models.runtime import WireModel

class GameJoinChallengeRequest(WireModel):
    playfab_id: str = Field(alias="playfab_id", json_schema_extra={"format": "", "nullable": False})
    commitment: str = Field(alias="commitment", json_schema_extra={"format": "", "nullable": False})
    audience: str = Field(alias="audience", json_schema_extra={"format": "", "nullable": False})
    target_ip: IPAddress = Field(alias="target_ip", json_schema_extra={"format": "ip-address", "nullable": False})
    target_port: int = Field(alias="target_port", json_schema_extra={"format": "", "nullable": False})
