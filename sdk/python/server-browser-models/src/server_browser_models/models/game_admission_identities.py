"""Generated from OpenAPI. DO NOT EDIT; run uv run server-browser-codegen."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union
from server_browser_models.models.game_platform_identity import GamePlatformIdentity

from server_browser_models.runtime import WireModel

class GameAdmissionIdentities(WireModel):
    playfab: str = Field(alias="playfab", json_schema_extra={"format": "", "nullable": False})
    eos_product_user_id: str = Field(alias="eos_product_user_id", json_schema_extra={"format": "", "nullable": False})
    platform: GamePlatformIdentity = Field(alias="platform", json_schema_extra={"format": "", "nullable": False})
