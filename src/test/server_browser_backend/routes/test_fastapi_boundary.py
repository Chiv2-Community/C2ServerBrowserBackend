"""Exercise the generated boundary without the legacy test-client adapter."""
import asyncio
import threading

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from server_browser_api.apis.api_v1_api import create_router
from server_browser_api.apis.api_v1_api_base import BaseApiV1Api
from server_browser_api.models import Mod, ServerListResponse, ServerRegistrationRequest
from server_browser_api.runtime import ApiResponse, contract
from server_browser_backend.main import app
from server_browser_backend.routes.api_v1 import BrowserApi
from server_browser_backend.routes import shared

from . import prepare_test_state


def test_generated_interface_rejects_incomplete_implementation():
    class Incomplete(BaseApiV1Api):
        pass

    with pytest.raises(TypeError, match="abstract"):
        Incomplete()  # type: ignore[abstract]
    with pytest.raises(TypeError):
        create_router()  # type: ignore[call-arg]
    assert not hasattr(BaseApiV1Api, "subclasses")


def test_routers_use_only_the_explicit_instance_and_keep_it_alive():
    calls = []

    class Implementation(BrowserApi):
        def __init__(self, name):
            self.name = name

        def before_operation(self, request: Request, operation_id: str) -> None:
            calls.append((self.name, operation_id))

        def get_servers(self, request: Request) -> ApiResponse[ServerListResponse]:
            assert request.client is not None
            calls.append((self.name, request.client.host))
            return ApiResponse(ServerListResponse(servers=[]))

    first = FastAPI()
    first.include_router(create_router(Implementation("first")))
    second = FastAPI()
    second.include_router(create_router(Implementation("second")))
    with TestClient(first) as client:
        assert client.get("/api/v1/servers").json() == {"servers": []}
        assert client.get("/api/v1/servers").status_code == 200
    with TestClient(second) as client:
        assert client.get("/api/v1/servers").status_code == 200
    assert calls == [
        ("first", "get_servers"), ("first", "testclient"),
        ("first", "get_servers"), ("first", "testclient"),
        ("second", "get_servers"), ("second", "testclient"),
    ]


def test_synchronous_handlers_do_not_execute_on_the_event_loop_thread():
    threads = []

    class Implementation(BrowserApi):
        def before_operation(self, request: Request, operation_id: str) -> None:
            threads.append(threading.get_ident())

        def get_servers(self, request: Request) -> ApiResponse[ServerListResponse]:
            threads.append(threading.get_ident())
            return ApiResponse(ServerListResponse(servers=[]))

    application = FastAPI()
    application.include_router(create_router(Implementation()))

    async def exercise():
        event_loop_thread = threading.get_ident()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url="http://test") as client:
            assert (await client.get("/api/v1/servers")).status_code == 200
        assert len(threads) == 2
        assert all(thread != event_loop_thread for thread in threads)

    asyncio.run(exercise())


def test_oas_is_authoritative_and_no_implicit_docs_routes_exist():
    assert app.openapi() == contract()
    with TestClient(app) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404


def test_general_exception_handler_preserves_debug_traceback(monkeypatch):
    prepare_test_state()
    monkeypatch.setattr(shared, "DEBUG_MODE", True)

    def fail_listing():
        raise RuntimeError("listing failed")

    monkeypatch.setattr(shared.server_list, "get_all", fail_listing)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/servers")
    assert response.status_code == 500
    body = response.json()
    assert body["message"] == "listing failed"
    assert "fail_listing" in body["stack"]
    assert "RuntimeError: listing failed" in body["stack"]


def test_forwarded_ip_uses_one_proxy_hop_and_does_not_leak_between_requests():
    prepare_test_state(ban_list=["192.0.2.2"])
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.get("/api/v1/servers", headers={"X-Forwarded-For": "192.0.2.1, 192.0.2.2"}).status_code == 403
        assert client.get("/api/v1/servers", headers={"X-Forwarded-For": "192.0.2.2, 192.0.2.1"}).status_code == 200
        assert client.get("/api/v1/servers").status_code == 200


@pytest.mark.parametrize("address", ["2001:db8::1", "2001:0db8:0:0:0:0:0:1", "[2001:db8::1]"])
def test_ban_check_parameter_accepts_equivalent_ipv6_literals(address):
    prepare_test_state(ban_list=["2001:db8::/64"])
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        response = client.get("/api/v1/check-banned/" + address)
        assert response.status_code == 200
        assert response.json() == {"banned": True}


def test_ban_check_rejects_a_hostname_as_an_ip_parameter():
    prepare_test_state()
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        response = client.get("/api/v1/check-banned/hostname.example")
        assert response.status_code == 400
        assert response.json()["status"] == "invalid_json_body"


def test_pydantic_defaults_are_independent_and_models_are_frozen():
    registration = {
        "ports": {"game": 1, "ping": 2, "a2s": 3}, "name": "server", "description": "",
        "current_map": "map", "player_count": 0, "max_players": 32,
    }
    first = ServerRegistrationRequest.from_json(registration)
    second = ServerRegistrationRequest.from_json(registration)
    assert first.mods == second.mods == [] and first.mods is not second.mods
    first.mods.append(Mod(name="first only", organization="test", version="1"))
    assert second.mods == []
    with pytest.raises(ValueError, match="frozen"):
        first.name = "changed"


@pytest.mark.parametrize("body", [b"{", b"null", b"[]", b'"body"'])
def test_malformed_requests_are_json_400_not_framework_422(body):
    prepare_test_state()
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        response = client.post("/api/v1/servers", content=body, headers={"Content-Type": "application/json"})
        assert response.status_code == 400
        assert response.json()["status"] in {"missing_json_body", "invalid_json_body"}
