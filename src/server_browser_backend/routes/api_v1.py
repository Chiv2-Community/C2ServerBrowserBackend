"""Application implementation of the generated API interface."""
from __future__ import annotations

from datetime import datetime
from ipaddress import ip_address
from importlib.resources import files
from typing import Callable
from uuid import uuid4
import traceback
import logging

from fastapi import Request, Response

from server_browser_api.apis.api_v1_api_base import BaseApiV1Api
from server_browser_api.models import (
    BanListResponse, BanStatusResponse, ErrorResponse, IpListRequest, JwksResponse,
    LoginRequest, LoginResponse, RegistrationResponse, ServerListResponse,
    ServerRegistrationRequest, StatusResponse, UpdateRegisteredServer,
    UpdateResponse, VerifiedListResponse,
)
from server_browser_api.runtime import (
    ApiResponse, IPAddress, DictKeyError, DictTypeError, JsonMissing, SchemaValidationError, render_response,
)
from server_browser_backend.iterable_util import find
from server_browser_backend.ip_list import IpList
from server_browser_backend.models.base_models import Server, server_listing, server_response
from server_browser_backend.routes.shared import (
    Banned, KEY_HEADER, RequestPolicy, get_ip,
)
from server_browser_backend.server_list import InvalidSecretKey, SecretKeyMissing, ServerList
from server_browser_backend.token_reissuer import TokenReissuer

logger = logging.getLogger(__name__)


def status(code: str, message: str, http_status: int) -> ApiResponse[StatusResponse]:
    return ApiResponse(StatusResponse(status=code, message=message), http_status)


def require_key(value: str | None) -> str:
    if not value:
        raise SecretKeyMissing()
    return value


class BrowserApi(BaseApiV1Api):
    def __init__(
        self, *, server_list: ServerList, ban_list: IpList, verified_list: IpList,
        policy: RequestPolicy, token_reissuer: TokenReissuer,
        show_registered_ips: Callable[[], bool],
    ):
        self.server_list = server_list
        self.ban_list = ban_list
        self.verified_list = verified_list
        self.policy = policy
        self.token_reissuer = token_reissuer
        self.show_registered_ips = show_registered_ips

    def before_operation(self, request: Request, operation_id: str) -> None:
        if operation_id not in {"jwks", "login"}:
            self.policy.get_and_validate_ip(request)

    def jwks(self, request: Request) -> ApiResponse[JwksResponse]:
        return ApiResponse(self.token_reissuer.get_jwks_response())

    def login(self, request: Request, login_request: LoginRequest) -> ApiResponse[LoginResponse]:
        token = self.token_reissuer.validate_and_reissue(login_request.token, get_ip(request))
        return ApiResponse(LoginResponse(token=token))

    def send_swagger(self, request: Request) -> ApiResponse[str]:
        spec = files("server_browser_api").joinpath("openapi.yaml")
        return ApiResponse(spec.read_text(), content_type="text/yaml")

    def check_banned(self, request: Request, ip: IPAddress) -> ApiResponse[BanStatusResponse]:
        return ApiResponse(BanStatusResponse(banned=self.ban_list.contains(str(ip))))

    def register(self, request: Request, server_registration_request: ServerRegistrationRequest) -> ApiResponse[RegistrationResponse] | ApiResponse[StatusResponse]:
        try:
            server = Server.create_after_registration(
                server_registration_request, str(uuid4()), get_ip(request), datetime.now().timestamp(),
            )
        except ValueError:
            return status("invalid_ip", "Invalid IP address", 400)
        if self.policy.is_whitelisted(request):
            server = server.verified()
        key = self.server_list.register(server)
        logger.info('Registered server "%s" at %s:%s', server.name, server.ip_address, server.ports.game)
        return ApiResponse(RegistrationResponse(
            key=key, refresh_before=server.last_heartbeat + self.server_list.heartbeat_timeout,
            server=server_response(server),
        ), 201)

    def heartbeat(self, request: Request, server_id: str, x_chiv2_server_browser_key: str | None) -> ApiResponse[UpdateResponse] | ApiResponse[StatusResponse]:
        return self._update_server(request, server_id, x_chiv2_server_browser_key, lambda server: server.with_heartbeat(datetime.now().timestamp()))

    def update(self, request: Request, server_id: str, update_registered_server: UpdateRegisteredServer, x_chiv2_server_browser_key: str | None) -> ApiResponse[UpdateResponse] | ApiResponse[StatusResponse]:
        return self._update_server(request, server_id, x_chiv2_server_browser_key, lambda server: server.with_update(update_registered_server))

    def delete_server(self, request: Request, server_id: str, x_chiv2_server_browser_key: str | None) -> ApiResponse[StatusResponse]:
        server = self.server_list.delete(server_id, require_key(x_chiv2_server_browser_key))
        if server is None:
            logger.warning('Deletion failed. Server with id %s not registered.', server_id)
            return status("not_registered", "server not registered", 404)
        logger.info('Deleted server "%s" at %s:%s', server.name, server.ip_address, server.ports.game)
        return status("deleted", "The server has been deleted", 200)

    def get_servers(self, request: Request) -> ApiResponse[ServerListResponse]:
        return ApiResponse(server_listing(self.server_list.get_all(), include_ip=self.show_registered_ips()))

    def add_to_ban_list(self, request: Request, ip_list_request: IpListRequest, x_chiv2_server_browser_admin_key: str | None) -> ApiResponse[BanListResponse] | ApiResponse[StatusResponse]:
        return self._change_ban_list(request, ip_list_request, x_chiv2_server_browser_admin_key, remove=False)

    def remove_from_ban_list(self, request: Request, ip_list_request: IpListRequest, x_chiv2_server_browser_admin_key: str | None) -> ApiResponse[BanListResponse] | ApiResponse[StatusResponse]:
        return self._change_ban_list(request, ip_list_request, x_chiv2_server_browser_admin_key, remove=True)

    def _change_ban_list(self, request: Request, body: IpListRequest, credential: str | None, remove: bool) -> ApiResponse[BanListResponse] | ApiResponse[StatusResponse]:
        key = credential or ""
        error = change_ip_list(request, self.ban_list, body.banned_ips, "banned_ips", "ban", key, remove)
        if error is not None:
            return error
        return ApiResponse(BanListResponse(banned_ips=[str(ip) for ip in self.ban_list.get_all(key)]))

    def get_ban_list(self, request: Request, x_chiv2_server_browser_admin_key: str | None) -> ApiResponse[BanListResponse] | ApiResponse[StatusResponse]:
        key = x_chiv2_server_browser_admin_key or ""
        if not self.ban_list.validate(key):
            return status("forbidden", "Invalid admin key", 403)
        return ApiResponse(BanListResponse(banned_ips=[str(ip) for ip in self.ban_list.get_all(key)]))

    def add_to_verified_list(self, request: Request, ip_list_request: IpListRequest, x_chiv2_server_browser_admin_key: str | None) -> ApiResponse[VerifiedListResponse] | ApiResponse[StatusResponse]:
        return self._change_verified_list(request, ip_list_request, x_chiv2_server_browser_admin_key, remove=False)

    def remove_from_verified_list(self, request: Request, ip_list_request: IpListRequest, x_chiv2_server_browser_admin_key: str | None) -> ApiResponse[VerifiedListResponse] | ApiResponse[StatusResponse]:
        return self._change_verified_list(request, ip_list_request, x_chiv2_server_browser_admin_key, remove=True)

    def _change_verified_list(self, request: Request, body: IpListRequest, credential: str | None, remove: bool) -> ApiResponse[VerifiedListResponse] | ApiResponse[StatusResponse]:
        key = credential or ""
        error = change_ip_list(request, self.verified_list, body.verified_ips, "verified_ips", "verified", key, remove)
        if error is not None:
            return error
        return ApiResponse(VerifiedListResponse(verified_ips=[str(ip) for ip in self.verified_list.get_all(key)]))

    def get_verified_list(self, request: Request, x_chiv2_server_browser_admin_key: str | None) -> ApiResponse[VerifiedListResponse] | ApiResponse[StatusResponse]:
        key = x_chiv2_server_browser_admin_key or ""
        if not self.verified_list.validate(key):
            return status("forbidden", "Invalid admin key", 403)
        return ApiResponse(VerifiedListResponse(verified_ips=[str(ip) for ip in self.verified_list.get_all(key)]))

    def _update_server(self, request: Request, server_id: str, credential: str | None, transform: Callable[[Server], Server]) -> ApiResponse[UpdateResponse] | ApiResponse[StatusResponse]:
        key = require_key(credential)
        existing = find(self.server_list.get_all(), lambda server: server.unique_id == server_id)
        if existing is None:
            logger.warning("Update failed: server %s is not registered", server_id)
            return status("not_registered", "server not registered", 404)
        if ip_address(get_ip(request)) != existing.ip_address:
            self.server_list.delete(server_id, key)
            logger.warning("Registration invalidated: requester IP changed for %s", server_id)
            return status("unauthorized", "Invalid IP address", 401)
        server = self.server_list.update(server_id, key, transform)
        if server is None:
            return status("not_registered", "server not registered", 400)
        logger.info("Update/heartbeat received for %s (%s)", server.name, server.unique_id)
        return ApiResponse(UpdateResponse(
            refresh_before=server.last_heartbeat + self.server_list.heartbeat_timeout,
            server=server_response(server),
        ))


def change_ip_list(request: Request, ip_list: IpList, ips: list[str] | None, field: str, label: str, key: str, remove: bool) -> ApiResponse[StatusResponse] | None:
    if ips is None:
        return status("invalid_request", f"{field} is required", 400)
    if not ip_list.validate(key):
        logger.warning("%s-list change denied for %s: invalid admin key", label.capitalize(), get_ip(request))
        return status("forbidden", "Invalid admin key", 403)
    if remove:
        if not ip_list.remove_all(key, ips):
            return status("forbidden", "Invalid admin key", 403)
    elif ip_list.add_all(key, ips) is None:
        return status("invalid_ip", "Invalid IP address", 400)
    logger.info("%s changed %s list: %s %s entries", get_ip(request), label, "remove" if remove else "add", len(ips))
    return None


async def handle_json_missing(request: Request, error: JsonMissing) -> Response:
    return render_response(status("missing_json_body", "JSON body is required", 400))


async def handle_dict_key_error(request: Request, error: DictKeyError) -> Response:
    return render_response(ApiResponse(StatusResponse(
        status="invalid_json_body", message=f"Missing key '{error.key}'", context=error.context,
    ), 400))


async def handle_dict_type_error(request: Request, error: DictTypeError) -> Response:
    message = f"Invalid type for key '{error.key}'. Got '{error.actual_type.__name__}' with value '{error.value}', but expected '{error.expected_type.__name__}'"
    return render_response(ApiResponse(StatusResponse(
        status="invalid_json_body", message=message, context=error.context,
    ), 400))


async def handle_secret_key_missing(request: Request, error: SecretKeyMissing) -> Response:
    return render_response(status("no_key", KEY_HEADER + " header not specified", 400))


async def handle_schema_validation(request: Request, error: SchemaValidationError) -> Response:
    return render_response(status("invalid_json_body", str(error), 400))


async def handle_invalid_secret_key(request: Request, error: InvalidSecretKey) -> Response:
    return render_response(status("forbidden", "Invalid secret key", 403))


async def handle_banned_user(request: Request, error: Banned) -> Response:
    return render_response(status("forbidden", "You are banned", 403))


async def handle_general_exception(request: Request, error: Exception, *, debug_mode: bool) -> Response:
    logger.error("Unhandled exception: %s", error, exc_info=True)
    if debug_mode:
        return render_response(ApiResponse(ErrorResponse(
            status="error", message=str(error), stack=traceback.format_exc(),
        ), 500))
    return render_response(status("error", "An unexpected error occurred.", 500))
