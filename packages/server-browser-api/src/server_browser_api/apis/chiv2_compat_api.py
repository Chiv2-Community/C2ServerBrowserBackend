"""Generated FastAPI router. DO NOT EDIT."""
from __future__ import annotations

from fastapi import APIRouter, Request, Response
from starlette.concurrency import run_in_threadpool
from server_browser_api.models.matchmake_request import MatchmakeRequest
from server_browser_api.models.motd_request import MotdRequest
from server_browser_api.models.playfab_error_response import PlayfabErrorResponse
from server_browser_api.models.playfab_matchmake_response import PlayfabMatchmakeResponse
from server_browser_api.models.status_response import StatusResponse
from server_browser_api.models.tbio_motd_response import TbioMotdResponse
from server_browser_api.models.tbio_server_list_response import TbioServerListResponse
from server_browser_api.apis.chiv2_compat_api_base import BaseChiv2CompatApi
from server_browser_api.runtime import read_body, read_parameter, render_response

def create_router(implementation: BaseChiv2CompatApi) -> APIRouter:
    router = APIRouter()

    @router.api_route("/api/tbio/GetCurrentGames", methods=["POST"] + (["HEAD"] if "POST" == "GET" else []), operation_id="tbio_get_servers", response_model=None)
    async def tbio_get_servers(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "tbio_get_servers")
        result = await run_in_threadpool(implementation.tbio_get_servers, request)
        return render_response(result)

    @router.api_route("/api/tbio/GetMotd", methods=["POST"] + (["HEAD"] if "POST" == "GET" else []), operation_id="get_motd", response_model=None)
    async def get_motd(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "get_motd")
        motd_request = MotdRequest.from_json(await read_body(request))
        result = await run_in_threadpool(implementation.get_motd, request, motd_request=motd_request)
        return render_response(result)

    @router.api_route("/api/playfab/Client/Matchmake", methods=["POST"] + (["HEAD"] if "POST" == "GET" else []), operation_id="playfab_client_matchmake", response_model=None)
    async def playfab_client_matchmake(request: Request) -> Response:
        await run_in_threadpool(implementation.before_operation, request, "playfab_client_matchmake")
        matchmake_request = MatchmakeRequest.from_json(await read_body(request))
        result = await run_in_threadpool(implementation.playfab_client_matchmake, request, matchmake_request=matchmake_request)
        return render_response(result)

    return router
