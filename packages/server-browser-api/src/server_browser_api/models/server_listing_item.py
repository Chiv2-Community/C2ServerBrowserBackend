"""Generated from OpenAPI. DO NOT EDIT; run scripts/generate_api.py."""
from __future__ import annotations

from pydantic import Field
from typing import Any, Dict, List, Optional, Union
from server_browser_api.models.chivalry2_ports import Chivalry2Ports
from server_browser_api.models.mod import Mod
from server_browser_api.models.server_response import ServerResponse
from server_browser_api.models.server_response_with_ip import ServerResponseWithIP
from server_browser_api.runtime import IPAddress

from server_browser_api.runtime import WireModel

ServerListingItem = Union[
    ServerResponse,
    ServerResponseWithIP,
]
