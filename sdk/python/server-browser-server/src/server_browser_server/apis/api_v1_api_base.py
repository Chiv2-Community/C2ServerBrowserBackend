"""Generated API interface. DO NOT EDIT."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from server_browser_server.runtime import ApiResponse, RequestContext
from pydantic import Field, StrictStr
from typing_extensions import Annotated
from server_browser_models.models.ban_list_response import BanListResponse
from server_browser_models.models.ban_status_response import BanStatusResponse
from server_browser_models.models.ip_list_request import IpListRequest
from server_browser_models.models.jwks_response import JwksResponse
from server_browser_models.models.login_request import LoginRequest
from server_browser_models.models.registration_response import RegistrationResponse
from server_browser_models.models.server_list_response import ServerListResponse
from server_browser_models.models.server_registration_request import ServerRegistrationRequest
from server_browser_models.models.status_response import StatusResponse
from server_browser_models.models.update_registered_server import UpdateRegisteredServer
from server_browser_models.models.update_response import UpdateResponse
from server_browser_models.models.verified_list_response import VerifiedListResponse
from server_browser_models.runtime import IPAddress, LegacyIPAddress

class BaseApiV1Api(ABC):
    def before_operation(self, request: RequestContext, operation_id: str) -> None:
        """Application policy hook, called before request decoding."""

    @abstractmethod
    def jwks(self, request: RequestContext) -> ApiResponse[JwksResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def login(self, request: RequestContext, *, login_request: LoginRequest) -> ApiResponse[StatusResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def send_swagger(self, request: RequestContext) -> ApiResponse[str] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def get_servers(self, request: RequestContext) -> ApiResponse[ServerListResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def register(self, request: RequestContext, *, server_registration_request: ServerRegistrationRequest) -> ApiResponse[StatusResponse] | ApiResponse[StatusResponse] | ApiResponse[RegistrationResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def update(self, request: RequestContext, *, x_chiv2_server_browser_key: str | None, server_id: str, update_registered_server: UpdateRegisteredServer) -> ApiResponse[StatusResponse] | ApiResponse[StatusResponse] | ApiResponse[StatusResponse] | ApiResponse[StatusResponse] | ApiResponse[UpdateResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def delete_server(self, request: RequestContext, *, x_chiv2_server_browser_key: str | None, server_id: str) -> ApiResponse[StatusResponse] | ApiResponse[StatusResponse] | ApiResponse[StatusResponse] | ApiResponse[StatusResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def heartbeat(self, request: RequestContext, *, x_chiv2_server_browser_key: str | None, server_id: str) -> ApiResponse[StatusResponse] | ApiResponse[StatusResponse] | ApiResponse[StatusResponse] | ApiResponse[StatusResponse] | ApiResponse[UpdateResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def check_banned(self, request: RequestContext, *, ip: IPAddress) -> ApiResponse[BanStatusResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def get_ban_list(self, request: RequestContext, *, x_chiv2_server_browser_admin_key: str | None) -> ApiResponse[StatusResponse] | ApiResponse[BanListResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def add_to_ban_list(self, request: RequestContext, *, x_chiv2_server_browser_admin_key: str | None, ip_list_request: IpListRequest) -> ApiResponse[StatusResponse] | ApiResponse[StatusResponse] | ApiResponse[BanListResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def remove_from_ban_list(self, request: RequestContext, *, x_chiv2_server_browser_admin_key: str | None, ip_list_request: IpListRequest) -> ApiResponse[StatusResponse] | ApiResponse[StatusResponse] | ApiResponse[BanListResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def get_verified_list(self, request: RequestContext, *, x_chiv2_server_browser_admin_key: str | None) -> ApiResponse[StatusResponse] | ApiResponse[VerifiedListResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def add_to_verified_list(self, request: RequestContext, *, x_chiv2_server_browser_admin_key: str | None, ip_list_request: IpListRequest) -> ApiResponse[StatusResponse] | ApiResponse[StatusResponse] | ApiResponse[VerifiedListResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError

    @abstractmethod
    def remove_from_verified_list(self, request: RequestContext, *, x_chiv2_server_browser_admin_key: str | None, ip_list_request: IpListRequest) -> ApiResponse[StatusResponse] | ApiResponse[StatusResponse] | ApiResponse[VerifiedListResponse] | ApiResponse[StatusResponse]:
        raise NotImplementedError
