"""Generated from OpenAPI. DO NOT EDIT; run scripts/generate_api.py."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union
from server_browser_api.models.server_response import ServerResponse

from server_browser_api.runtime import WireModel

class RegistrationResponse(WireModel):
    key: str = Field(alias="key", json_schema_extra={"format": "", "nullable": False})
    refresh_before: float = Field(alias="refresh_before", json_schema_extra={"format": "double", "nullable": False})
    server: ServerResponse = Field(alias="server", json_schema_extra={"format": "", "nullable": False})
