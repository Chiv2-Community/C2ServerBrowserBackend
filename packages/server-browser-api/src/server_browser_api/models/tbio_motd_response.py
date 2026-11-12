"""Generated from OpenAPI. DO NOT EDIT; run scripts/generate_api.py."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union

from server_browser_api.runtime import WireModel

class TbioMotdResponse(WireModel):
    success: bool = Field(alias="Success", json_schema_extra={"format": "", "nullable": False})
    data: Dict[str, object] = Field(alias="Data", json_schema_extra={"format": "", "nullable": False})
    expiration: int = Field(alias="expiration", json_schema_extra={"format": "", "nullable": False})
