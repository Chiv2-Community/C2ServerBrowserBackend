"""Generated from OpenAPI. DO NOT EDIT; run scripts/generate_api.py."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union

from server_browser_api.runtime import WireModel

class MotdRequest(WireModel):
    language: str = Field(default_factory=lambda: 'en', alias="Language", json_schema_extra={"format": "", "nullable": False})
