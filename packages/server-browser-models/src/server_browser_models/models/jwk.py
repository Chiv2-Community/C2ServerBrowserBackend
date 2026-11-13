"""Generated from OpenAPI. DO NOT EDIT; run scripts/generate_api.py."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union

from server_browser_models.runtime import WireModel

class Jwk(WireModel):
    kty: str = Field(alias="kty", json_schema_extra={"format": "", "nullable": False})
    alg: str = Field(alias="alg", json_schema_extra={"format": "", "nullable": False})
    use: str = Field(alias="use", json_schema_extra={"format": "", "nullable": False})
    kid: str = Field(alias="kid", json_schema_extra={"format": "", "nullable": False})
    n: str = Field(alias="n", json_schema_extra={"format": "", "nullable": False})
    e: str = Field(alias="e", json_schema_extra={"format": "", "nullable": False})
