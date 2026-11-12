"""Generated from OpenAPI. DO NOT EDIT; run scripts/generate_api.py."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union

from server_browser_api.runtime import WireModel

class BanListResponse(WireModel):
    banned_ips: List[str] = Field(alias="banned_ips", json_schema_extra={"format": "", "nullable": False})
