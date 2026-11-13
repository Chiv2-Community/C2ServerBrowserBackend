"""Generated from OpenAPI. DO NOT EDIT; run scripts/generate_api.py."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union

from server_browser_api.runtime import WireModel

class PlayfabErrorResponse(WireModel):
    code: int = Field(alias="code", json_schema_extra={"format": "", "nullable": False})
    data: Dict[str, object] = Field(alias="data", json_schema_extra={"format": "", "nullable": False})
    message: str = Field(alias="message", json_schema_extra={"format": "", "nullable": False})
    params: Dict[str, object] = Field(alias="params", json_schema_extra={"format": "", "nullable": False})
    success: bool = Field(alias="success", json_schema_extra={"format": "", "nullable": False})
