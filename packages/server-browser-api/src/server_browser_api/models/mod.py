"""Generated from OpenAPI. DO NOT EDIT; run scripts/generate_api.py."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union

from server_browser_api.runtime import WireModel

class Mod(WireModel):
    name: str = Field(alias="name", json_schema_extra={"format": "", "nullable": False})
    organization: str = Field(alias="organization", json_schema_extra={"format": "", "nullable": False})
    version: str = Field(alias="version", json_schema_extra={"format": "", "nullable": False})
    active: bool = Field(default_factory=lambda: False, alias="active", json_schema_extra={"format": "", "nullable": False})
