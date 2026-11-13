"""Generated from OpenAPI. DO NOT EDIT; run uv run server-browser-codegen."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union

from server_browser_models.runtime import WireModel

class IpListRequest(WireModel):
    banned_ips: List[str] | None = Field(default=None, alias="banned_ips", json_schema_extra={"format": "", "nullable": False})
    verified_ips: List[str] | None = Field(default=None, alias="verified_ips", json_schema_extra={"format": "", "nullable": False})
