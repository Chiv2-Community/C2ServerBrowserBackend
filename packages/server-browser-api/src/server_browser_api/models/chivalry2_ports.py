"""Generated from OpenAPI. DO NOT EDIT; run scripts/generate_api.py."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union

from server_browser_api.runtime import WireModel

class Chivalry2Ports(WireModel):
    game: int = Field(alias="game", json_schema_extra={"format": "int32", "nullable": False})
    a2s: int = Field(alias="a2s", json_schema_extra={"format": "int32", "nullable": False})
    ping: int = Field(alias="ping", json_schema_extra={"format": "int32", "nullable": False})
