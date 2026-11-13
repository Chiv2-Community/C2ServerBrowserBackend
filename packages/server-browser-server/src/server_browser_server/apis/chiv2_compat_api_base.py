"""Generated API interface. DO NOT EDIT."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from server_browser_server.runtime import ApiResponse, RequestContext
from server_browser_models.models.matchmake_request import MatchmakeRequest
from server_browser_models.models.motd_request import MotdRequest
from server_browser_models.models.playfab_error_response import PlayfabErrorResponse
from server_browser_models.models.playfab_matchmake_response import PlayfabMatchmakeResponse
from server_browser_models.models.status_response import StatusResponse
from server_browser_models.models.tbio_motd_response import TbioMotdResponse
from server_browser_models.models.tbio_server_list_response import TbioServerListResponse
from server_browser_models.runtime import IPAddress, LegacyIPAddress

class BaseChiv2CompatApi(ABC):
    def before_operation(self, request: RequestContext, operation_id: str) -> None:
        """Application policy hook, called before request decoding."""

    @abstractmethod
    def tbio_get_servers(self, request: RequestContext) -> ApiResponse[TbioServerListResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def get_motd(self, request: RequestContext, *, motd_request: MotdRequest) -> ApiResponse[TbioMotdResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def playfab_client_matchmake(self, request: RequestContext, *, matchmake_request: MatchmakeRequest) -> ApiResponse[StatusResponse] | ApiResponse[PlayfabErrorResponse] | ApiResponse[PlayfabMatchmakeResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError
