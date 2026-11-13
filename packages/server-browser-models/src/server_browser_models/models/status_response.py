"""Generated from OpenAPI. DO NOT EDIT; run scripts/generate_api.py."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union

from server_browser_models.runtime import WireModel

class StatusResponse(WireModel):
    status: str = Field(alias="status", json_schema_extra={"format": "", "nullable": False})
    message: str = Field(alias="message", json_schema_extra={"format": "", "nullable": False})
    context: Dict[str, object] | None = Field(default=None, alias="context", json_schema_extra={"format": "", "nullable": True})
