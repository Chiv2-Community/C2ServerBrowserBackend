"""Generated from OpenAPI. DO NOT EDIT; run uv run server-browser-codegen."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union

from server_browser_models.runtime import WireModel

class GameJoinChallengeResponse(WireModel):
    challenge_id: str = Field(alias="challenge_id", json_schema_extra={"format": "", "nullable": False})
    server_id: str = Field(alias="server_id", json_schema_extra={"format": "", "nullable": False})
    expires_at: int = Field(alias="expires_at", json_schema_extra={"format": "int64", "nullable": False})
