"""Generated from OpenAPI. DO NOT EDIT; run uv run server-browser-codegen."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union
from server_browser_models.models.tbio_server_list_data import TbioServerListData

from server_browser_models.runtime import WireModel

class TbioServerListResponse(WireModel):
    success: bool = Field(alias="Success", json_schema_extra={"format": "", "nullable": False})
    data: TbioServerListData = Field(alias="Data", json_schema_extra={"format": "", "nullable": False})
