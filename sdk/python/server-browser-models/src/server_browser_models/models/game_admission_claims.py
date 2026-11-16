"""Generated from OpenAPI. DO NOT EDIT; run uv run server-browser-codegen."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union
from server_browser_models.models.game_admission_identities import GameAdmissionIdentities

from server_browser_models.runtime import WireModel

class GameAdmissionClaims(WireModel):
    iss: str = Field(alias="iss", json_schema_extra={"format": "", "nullable": False})
    sub: str = Field(alias="sub", json_schema_extra={"format": "", "nullable": False})
    aud: str = Field(alias="aud", json_schema_extra={"format": "", "nullable": False})
    purpose: str = Field(alias="purpose", json_schema_extra={"format": "", "nullable": False})
    version: int = Field(alias="version", json_schema_extra={"format": "", "nullable": False})
    identities: GameAdmissionIdentities = Field(alias="identities", json_schema_extra={"format": "", "nullable": False})
    iat: int = Field(alias="iat", json_schema_extra={"format": "int64", "nullable": False})
    nbf: int = Field(alias="nbf", json_schema_extra={"format": "int64", "nullable": False})
    exp: int = Field(alias="exp", json_schema_extra={"format": "int64", "nullable": False})
    jti: str = Field(alias="jti", json_schema_extra={"format": "", "nullable": False})
