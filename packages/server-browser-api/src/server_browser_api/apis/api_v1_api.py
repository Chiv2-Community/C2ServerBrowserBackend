"""Generated FastAPI router. DO NOT EDIT."""
from __future__ import annotations

from fastapi import APIRouter, Request, Response
from starlette.concurrency import run_in_threadpool
from pydantic import Field, StrictStr
from typing_extensions import Annotated
from server_browser_api.models.ban_list_response import BanListResponse
from server_browser_api.models.ban_status_response import BanStatusResponse
from server_browser_api.models.ip_list_request import IpListRequest
from server_browser_api.models.jwks_response import JwksResponse
from server_browser_api.models.login_request import LoginRequest
from server_browser_api.models.login_response import LoginResponse
from server_browser_api.models.registration_response import RegistrationResponse
from server_browser_api.models.server_list_response import ServerListResponse
from server_browser_api.models.server_registration_request import ServerRegistrationRequest
from server_browser_api.models.status_response import StatusResponse
from server_browser_api.models.update_registered_server import UpdateRegisteredServer
from server_browser_api.models.update_response import UpdateResponse
from server_browser_api.models.verified_list_response import VerifiedListResponse
from server_browser_api.apis.api_v1_api_base import BaseApiV1Api
from server_browser_api.runtime import decode_model, read_body, read_parameter, render_response

def create_router(implementation: BaseApiV1Api) -> APIRouter:
    router = APIRouter()

    @router.api_route("/api/v1/auth/jwks.json", methods=["GET"] + (["HEAD"] if "GET" == "GET" else []), operation_id="jwks", response_model=None)
    async def jwks(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "jwks")
        result = await run_in_threadpool(implementation.jwks, request)
        return render_response(result)

    @router.api_route("/api/v1/auth/login", methods=["POST"] + (["HEAD"] if "POST" == "GET" else []), operation_id="login", response_model=None)
    async def login(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "login")
        login_request = decode_model(LoginRequest, await read_body(request))
        result = await run_in_threadpool(implementation.login, request, login_request=login_request)
        return render_response(result)

    @router.api_route("/api/v1/swagger.yaml", methods=["GET"] + (["HEAD"] if "GET" == "GET" else []), operation_id="send_swagger", response_model=None)
    async def send_swagger(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "send_swagger")
        result = await run_in_threadpool(implementation.send_swagger, request)
        return render_response(result)

    @router.api_route("/api/v1/servers", methods=["GET"] + (["HEAD"] if "GET" == "GET" else []), operation_id="get_servers", response_model=None)
    async def get_servers(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "get_servers")
        result = await run_in_threadpool(implementation.get_servers, request)
        return render_response(result)

    @router.api_route("/api/v1/servers", methods=["POST"] + (["HEAD"] if "POST" == "GET" else []), operation_id="register", response_model=None)
    async def register(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "register")
        server_registration_request = decode_model(ServerRegistrationRequest, await read_body(request))
        result = await run_in_threadpool(implementation.register, request, server_registration_request=server_registration_request)
        return render_response(result)

    @router.api_route("/api/v1/servers/{server_id}", methods=["PUT"] + (["HEAD"] if "PUT" == "GET" else []), operation_id="update", response_model=None)
    async def update(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "update")
        update_registered_server = decode_model(UpdateRegisteredServer, await read_body(request))
        x_chiv2_server_browser_key = read_parameter("update", "header", "X-CHIV2-SERVER-BROWSER-KEY", request.headers.get("X-CHIV2-SERVER-BROWSER-KEY"), application_validated=True)
        server_id = read_parameter("update", "path", "server_id", request.path_params.get("server_id"))
        result = await run_in_threadpool(implementation.update, request, x_chiv2_server_browser_key=x_chiv2_server_browser_key, server_id=server_id, update_registered_server=update_registered_server)
        return render_response(result)

    @router.api_route("/api/v1/servers/{server_id}", methods=["DELETE"] + (["HEAD"] if "DELETE" == "GET" else []), operation_id="delete_server", response_model=None)
    async def delete_server(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "delete_server")
        x_chiv2_server_browser_key = read_parameter("delete_server", "header", "X-CHIV2-SERVER-BROWSER-KEY", request.headers.get("X-CHIV2-SERVER-BROWSER-KEY"), application_validated=True)
        server_id = read_parameter("delete_server", "path", "server_id", request.path_params.get("server_id"))
        result = await run_in_threadpool(implementation.delete_server, request, x_chiv2_server_browser_key=x_chiv2_server_browser_key, server_id=server_id)
        return render_response(result)

    @router.api_route("/api/v1/servers/{server_id}/heartbeat", methods=["POST"] + (["HEAD"] if "POST" == "GET" else []), operation_id="heartbeat", response_model=None)
    async def heartbeat(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "heartbeat")
        x_chiv2_server_browser_key = read_parameter("heartbeat", "header", "X-CHIV2-SERVER-BROWSER-KEY", request.headers.get("X-CHIV2-SERVER-BROWSER-KEY"), application_validated=True)
        server_id = read_parameter("heartbeat", "path", "server_id", request.path_params.get("server_id"))
        result = await run_in_threadpool(implementation.heartbeat, request, x_chiv2_server_browser_key=x_chiv2_server_browser_key, server_id=server_id)
        return render_response(result)

    @router.api_route("/api/v1/check-banned/{ip}", methods=["GET"] + (["HEAD"] if "GET" == "GET" else []), operation_id="check_banned", response_model=None)
    async def check_banned(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "check_banned")
        ip = read_parameter("check_banned", "path", "ip", request.path_params.get("ip"))
        result = await run_in_threadpool(implementation.check_banned, request, ip=ip)
        return render_response(result)

    @router.api_route("/api/v1/admin/ban-list", methods=["GET"] + (["HEAD"] if "GET" == "GET" else []), operation_id="get_ban_list", response_model=None)
    async def get_ban_list(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "get_ban_list")
        x_chiv2_server_browser_admin_key = read_parameter("get_ban_list", "header", "X-CHIV2-SERVER-BROWSER-ADMIN-KEY", request.headers.get("X-CHIV2-SERVER-BROWSER-ADMIN-KEY"), application_validated=True)
        result = await run_in_threadpool(implementation.get_ban_list, request, x_chiv2_server_browser_admin_key=x_chiv2_server_browser_admin_key)
        return render_response(result)

    @router.api_route("/api/v1/admin/ban-list", methods=["PUT"] + (["HEAD"] if "PUT" == "GET" else []), operation_id="add_to_ban_list", response_model=None)
    async def add_to_ban_list(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "add_to_ban_list")
        ip_list_request = decode_model(IpListRequest, await read_body(request))
        x_chiv2_server_browser_admin_key = read_parameter("add_to_ban_list", "header", "X-CHIV2-SERVER-BROWSER-ADMIN-KEY", request.headers.get("X-CHIV2-SERVER-BROWSER-ADMIN-KEY"), application_validated=True)
        result = await run_in_threadpool(implementation.add_to_ban_list, request, x_chiv2_server_browser_admin_key=x_chiv2_server_browser_admin_key, ip_list_request=ip_list_request)
        return render_response(result)

    @router.api_route("/api/v1/admin/ban-list", methods=["DELETE"] + (["HEAD"] if "DELETE" == "GET" else []), operation_id="remove_from_ban_list", response_model=None)
    async def remove_from_ban_list(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "remove_from_ban_list")
        ip_list_request = decode_model(IpListRequest, await read_body(request))
        x_chiv2_server_browser_admin_key = read_parameter("remove_from_ban_list", "header", "X-CHIV2-SERVER-BROWSER-ADMIN-KEY", request.headers.get("X-CHIV2-SERVER-BROWSER-ADMIN-KEY"), application_validated=True)
        result = await run_in_threadpool(implementation.remove_from_ban_list, request, x_chiv2_server_browser_admin_key=x_chiv2_server_browser_admin_key, ip_list_request=ip_list_request)
        return render_response(result)

    @router.api_route("/api/v1/admin/verified-list", methods=["GET"] + (["HEAD"] if "GET" == "GET" else []), operation_id="get_verified_list", response_model=None)
    async def get_verified_list(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "get_verified_list")
        x_chiv2_server_browser_admin_key = read_parameter("get_verified_list", "header", "X-CHIV2-SERVER-BROWSER-ADMIN-KEY", request.headers.get("X-CHIV2-SERVER-BROWSER-ADMIN-KEY"), application_validated=True)
        result = await run_in_threadpool(implementation.get_verified_list, request, x_chiv2_server_browser_admin_key=x_chiv2_server_browser_admin_key)
        return render_response(result)

    @router.api_route("/api/v1/admin/verified-list", methods=["PUT"] + (["HEAD"] if "PUT" == "GET" else []), operation_id="add_to_verified_list", response_model=None)
    async def add_to_verified_list(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "add_to_verified_list")
        ip_list_request = decode_model(IpListRequest, await read_body(request))
        x_chiv2_server_browser_admin_key = read_parameter("add_to_verified_list", "header", "X-CHIV2-SERVER-BROWSER-ADMIN-KEY", request.headers.get("X-CHIV2-SERVER-BROWSER-ADMIN-KEY"), application_validated=True)
        result = await run_in_threadpool(implementation.add_to_verified_list, request, x_chiv2_server_browser_admin_key=x_chiv2_server_browser_admin_key, ip_list_request=ip_list_request)
        return render_response(result)

    @router.api_route("/api/v1/admin/verified-list", methods=["DELETE"] + (["HEAD"] if "DELETE" == "GET" else []), operation_id="remove_from_verified_list", response_model=None)
    async def remove_from_verified_list(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "remove_from_verified_list")
        ip_list_request = decode_model(IpListRequest, await read_body(request))
        x_chiv2_server_browser_admin_key = read_parameter("remove_from_verified_list", "header", "X-CHIV2-SERVER-BROWSER-ADMIN-KEY", request.headers.get("X-CHIV2-SERVER-BROWSER-ADMIN-KEY"), application_validated=True)
        result = await run_in_threadpool(implementation.remove_from_verified_list, request, x_chiv2_server_browser_admin_key=x_chiv2_server_browser_admin_key, ip_list_request=ip_list_request)
        return render_response(result)

    return router
