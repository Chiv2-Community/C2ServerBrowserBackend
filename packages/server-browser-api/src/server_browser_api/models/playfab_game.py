"""Generated from OpenAPI. DO NOT EDIT; run scripts/generate_api.py."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union
from server_browser_api.runtime import IPAddress

from server_browser_api.runtime import WireModel

class PlayfabGame(WireModel):
    server_hostname: IPAddress = Field(alias="ServerHostname", json_schema_extra={"format": "ip-address", "nullable": False})
    server_ipv4_address: IPAddress = Field(alias="ServerIPV4Address", json_schema_extra={"format": "ip-address", "nullable": False})
    server_port: int = Field(alias="ServerPort", json_schema_extra={"format": "", "nullable": False})
    ticket: str = Field(alias="Ticket", json_schema_extra={"format": "", "nullable": False})
