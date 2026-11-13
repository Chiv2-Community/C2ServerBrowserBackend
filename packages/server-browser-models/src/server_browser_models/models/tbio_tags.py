"""Generated from OpenAPI. DO NOT EDIT; run scripts/generate_api.py."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union

from server_browser_models.runtime import WireModel

class TbioTags(WireModel):
    build_id_s: str = Field(alias="BuildId_s", json_schema_extra={"format": "", "nullable": False})
    server_name_s: str = Field(alias="ServerName_s", json_schema_extra={"format": "", "nullable": False})
    region_s: str = Field(alias="Region_s", json_schema_extra={"format": "", "nullable": False})
    official_b: str = Field(alias="OFFICIAL_b", json_schema_extra={"format": "", "nullable": False})
    platform_s: str = Field(alias="Platform_s", json_schema_extra={"format": "", "nullable": False})
    ffa_b: str = Field(alias="FFA_b", json_schema_extra={"format": "", "nullable": False})
    ms_i: str = Field(alias="MS_i", json_schema_extra={"format": "", "nullable": False})
    map_name_s: str = Field(alias="MapName_s", json_schema_extra={"format": "", "nullable": False})
    ping_port_i: str = Field(alias="PingPort_i", json_schema_extra={"format": "", "nullable": False})
    query_port_i: str = Field(alias="QueryPort_i", json_schema_extra={"format": "", "nullable": False})
    t0_c: str = Field(alias="T0_c", json_schema_extra={"format": "", "nullable": False})
    pp_b: str = Field(alias="pp_b", json_schema_extra={"format": "", "nullable": False})
    t1_c: str = Field(alias="t1_c", json_schema_extra={"format": "", "nullable": False})
    mtim_i: str = Field(alias="MTIM_i", json_schema_extra={"format": "", "nullable": False})
