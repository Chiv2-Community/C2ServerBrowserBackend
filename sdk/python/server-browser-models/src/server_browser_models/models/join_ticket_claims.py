"""Generated from OpenAPI. DO NOT EDIT; run uv run server-browser-codegen."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union

from server_browser_models.runtime import WireModel

class JoinTicketClaims(WireModel):
    iss: str = Field(alias="iss", json_schema_extra={"format": "", "nullable": False})
    sub: str = Field(alias="sub", json_schema_extra={"format": "", "nullable": False})
    aud: str = Field(alias="aud", json_schema_extra={"format": "", "nullable": False})
    purpose: str = Field(alias="purpose", json_schema_extra={"format": "", "nullable": False})
    auth_time: int = Field(alias="auth_time", json_schema_extra={"format": "int64", "nullable": False})
    iat: int = Field(alias="iat", json_schema_extra={"format": "int64", "nullable": False})
    nbf: int = Field(alias="nbf", json_schema_extra={"format": "int64", "nullable": False})
    exp: int = Field(alias="exp", json_schema_extra={"format": "int64", "nullable": False})
    jti: str = Field(alias="jti", json_schema_extra={"format": "", "nullable": False})
