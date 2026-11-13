"""Generated from OpenAPI. DO NOT EDIT; run uv run server-browser-codegen."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union
from server_browser_models.models.jwk import Jwk

from server_browser_models.runtime import WireModel

class JwksResponse(WireModel):
    keys: List[Jwk] = Field(alias="keys", json_schema_extra={"format": "", "nullable": False})
