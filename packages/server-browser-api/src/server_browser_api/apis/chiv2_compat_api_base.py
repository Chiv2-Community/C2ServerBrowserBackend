"""Generated API interface. DO NOT EDIT."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from fastapi import Request
from server_browser_api.models.matchmake_request import MatchmakeRequest
from server_browser_api.models.motd_request import MotdRequest
from server_browser_api.models.playfab_error_response import PlayfabErrorResponse
from server_browser_api.models.playfab_matchmake_response import PlayfabMatchmakeResponse
from server_browser_api.models.status_response import StatusResponse
from server_browser_api.models.tbio_motd_response import TbioMotdResponse
from server_browser_api.models.tbio_server_list_response import TbioServerListResponse
from server_browser_api.runtime import ApiResponse, IPAddress, LegacyIPAddress

class BaseChiv2CompatApi(ABC):
    def before_operation(self, request: Request, operation_id: str) -> None:
        """Application policy hook, called before request decoding."""

    @abstractmethod
    def tbio_get_servers(self, request: Request) -> ApiResponse[TbioServerListResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def get_motd(self, request: Request, *, motd_request: MotdRequest) -> ApiResponse[TbioMotdResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def playfab_client_matchmake(self, request: Request, *, matchmake_request: MatchmakeRequest) -> ApiResponse[PlayfabErrorResponse] | ApiResponse[PlayfabErrorResponse] | ApiResponse[PlayfabMatchmakeResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError
