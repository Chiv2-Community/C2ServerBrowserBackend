"""Generated from OpenAPI. DO NOT EDIT; run uv run server-browser-codegen."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union
from server_browser_models.models.external_account import ExternalAccount

from server_browser_models.runtime import WireModel

class EosIdTokenPayload(WireModel):
    sub: str = Field(alias="sub", json_schema_extra={"format": "", "nullable": False})
    pfsid: str = Field(alias="pfsid", json_schema_extra={"format": "", "nullable": False})
    iss: str = Field(alias="iss", json_schema_extra={"format": "", "nullable": False})
    dn: str = Field(alias="dn", json_schema_extra={"format": "", "nullable": False})
    nonce: str = Field(alias="nonce", json_schema_extra={"format": "", "nullable": False})
    pfpid: str = Field(alias="pfpid", json_schema_extra={"format": "", "nullable": False})
    aud: str = Field(alias="aud", json_schema_extra={"format": "", "nullable": False})
    pfdid: str = Field(alias="pfdid", json_schema_extra={"format": "", "nullable": False})
    appid: str = Field(alias="appid", json_schema_extra={"format": "", "nullable": False})
    exp: int = Field(alias="exp", json_schema_extra={"format": "", "nullable": False})
    iat: int = Field(alias="iat", json_schema_extra={"format": "", "nullable": False})
    jti: str = Field(alias="jti", json_schema_extra={"format": "", "nullable": False})
    act: ExternalAccount | None = Field(default=None, alias="act", json_schema_extra={"format": "", "nullable": True})
