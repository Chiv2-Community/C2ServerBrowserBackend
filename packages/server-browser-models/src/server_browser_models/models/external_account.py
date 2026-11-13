"""Generated from OpenAPI. DO NOT EDIT; run uv run server-browser-codegen."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union

from server_browser_models.runtime import WireModel

class ExternalAccount(WireModel):
    eat: str = Field(alias="eat", json_schema_extra={"format": "", "nullable": False})
    eaid: str = Field(alias="eaid", json_schema_extra={"format": "", "nullable": False})
    pltfm: str = Field(alias="pltfm", json_schema_extra={"format": "", "nullable": False})
    dty: str = Field(alias="dty", json_schema_extra={"format": "", "nullable": False})
