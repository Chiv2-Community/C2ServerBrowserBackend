"""Generated clients exercise shared models through the actual FastAPI adapter."""
import asyncio
import inspect
import json
from ipaddress import IPv6Address

import httpx
import pytest
from fastapi.testclient import TestClient

from server_browser_client import AsyncClient, Client, ClientDecodeError
from server_browser_client.runtime import UNSET, request_arguments
from server_browser_models.models import (
    BanStatusResponse, Chivalry2Ports, IpListRequest, LoginRequest,
    MatchmakeRequest, MotdRequest, PlayfabGame, RegistrationResponse,
    ServerRegistrationRequest, StatusResponse, UpdateRegisteredServer,
)
from server_browser_models.runtime import contract


@pytest.mark.parametrize("asynchronous", [False, True])
def test_all_generated_operations_round_trip(app, browser, admin_key, monkeypatch, asynchronous):
    with TestClient(app, client=("2001:db8::1", 50000)) as backend:
        def transport(request):
            response = backend.request(
                request.method, str(request.url), headers=request.headers, content=request.content,
            )
            return httpx.Response(response.status_code, headers=response.headers, content=response.content)

        async def exercise():
            if asynchronous:
                session = httpx.AsyncClient(transport=httpx.ASGITransport(app, client=("2001:db8::1", 50000)))
                sdk = AsyncClient("http://test", session=session, headers={"x-chiv2-server-browser-admin-key": admin_key})
            else:
                session = httpx.Client(transport=httpx.MockTransport(transport))
                sdk = Client("http://test", session=session, headers={"x-chiv2-server-browser-admin-key": admin_key})
            called = set()

            async def call(name, **parameters):
                called.add(name)
                result = getattr(sdk, name)(**parameters)
                return await result if inspect.isawaitable(result) else result

            try:
                assert (await call("jwks")).body.keys == []
                login = await call("login", login_request=LoginRequest(token="eos-token"))
                assert login.status == 410
                assert isinstance(login.body, StatusResponse)
                assert login.body.status == "auth_retired"
                assert "openapi:" in (await call("send_swagger")).body
                assert (await call("get_servers")).body.servers == []
                registration = await call("register", server_registration_request=ServerRegistrationRequest(
                    name="sdk", description="", current_map="Map", player_count=0, max_players=32,
                    local_ip_address=IPv6Address("fd00::1"),
                    ports=Chivalry2Ports(game=7777, ping=7778, a2s=7779),
                ))
                assert registration.status == 201
                assert isinstance(registration.body, RegistrationResponse)
                server_id = registration.body.server.unique_id
                credentials = {"server_id": server_id, "x_chiv2_server_browser_key": registration.body.key}
                update = await call("update", **credentials, update_registered_server=UpdateRegisteredServer(
                    current_map="New Map", player_count=1, max_players=32,
                ))
                assert update.body.server.current_map == "New Map"
                assert (await call("heartbeat", **credentials)).status == 200
                tbio = await call("tbio_get_servers")
                assert tbio.body.data.games[0].server_hostname == IPv6Address("fd00::1")
                assert tbio.response.json()["Data"]["Games"][0]["ServerHostname"] == "[fd00::1]"
                playfab = await call("playfab_client_matchmake", matchmake_request=MatchmakeRequest(lobby_id=server_id))
                assert isinstance(playfab.body.data, PlayfabGame)
                assert playfab.response.json()["data"]["ServerHostname"] == "fd00::1"
                assert (await call("get_motd", motd_request=MotdRequest())).body.success
                assert isinstance((await call("check_banned", ip=IPv6Address("2001:db8::1"))).body, BanStatusResponse)
                for name, field in (("ban", "banned_ips"), ("verified", "verified_ips")):
                    body = IpListRequest(**{field: ["198.51.100.1"]})
                    assert (await call(f"add_to_{name}_list", ip_list_request=body)).status == 200
                    assert getattr((await call(f"get_{name}_list")).body, field)
                    assert (await call(f"remove_from_{name}_list", ip_list_request=body)).status == 200
                    # A per-call header must override a differently cased configured header.
                    denied = await call(f"get_{name}_list", x_chiv2_server_browser_admin_key="wrong")
                    assert denied.status == 403
                    assert isinstance(denied.body, StatusResponse)
                assert (await call("delete_server", **credentials)).body.status == "deleted"
                assert (await call("get_servers")).body.servers == []
                expected = {
                    operation["operationId"] for path in contract()["paths"].values()
                    for operation in path.values() if isinstance(operation, dict) and "operationId" in operation
                }
                assert called == expected
                assert all(hasattr(Client, name) and hasattr(AsyncClient, name) for name in expected)
            finally:
                if asynchronous:
                    await sdk.aclose()
                    assert not session.is_closed
                    await session.aclose()
                else:
                    sdk.close()
                    assert not session.is_closed
                    session.close()

        asyncio.run(exercise())


def test_client_preserves_omission_and_explicit_null():
    missing = request_arguments("get_motd", {}, UNSET)
    null = request_arguments("get_motd", {}, None)
    assert "content" not in missing
    assert null["content"] == b"null"
    assert null["headers"]["Content-Type"] == "application/json"
    omitted = request_arguments("get_motd", {}, MotdRequest())
    assert json.loads(omitted["content"]) == {}
    fields = dict(
        name="sdk", description="", current_map="Map", player_count=0, max_players=32,
        ports=Chivalry2Ports(game=7777, ping=7778, a2s=7779),
    )
    omitted_registration = ServerRegistrationRequest(**fields)
    null_registration = ServerRegistrationRequest(**fields, local_ip_address=None)
    omitted = json.loads(request_arguments("register", {}, omitted_registration)["content"])
    explicit_null = json.loads(request_arguments("register", {}, null_registration)["content"])
    assert "local_ip_address" not in omitted
    assert explicit_null["local_ip_address"] is None


@pytest.mark.parametrize("body", [{}, {"servers": "invalid"}, "invalid", None])
def test_invalid_declared_response_retains_raw_response(body):
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
        200, content=json.dumps(body), headers={"content-type": "application/json"},
    ))) as session:
        with pytest.raises(ClientDecodeError) as error:
            Client("http://test", session=session).get_servers()
        assert error.value.response.status_code == 200
        assert error.value.response.json() == body


def test_unexpected_response_retains_status_headers_and_body_without_retry():
    requests = []

    def reply(request):
        requests.append(request)
        return httpx.Response(502, headers={"x-request-id": "trace"}, content=b"upstream unavailable")

    with httpx.Client(transport=httpx.MockTransport(reply)) as session:
        result = Client("http://test", session=session).get_servers()
    assert result.body is None
    assert result.status == 502
    assert result.headers["x-request-id"] == "trace"
    assert result.response.content == b"upstream unavailable"
    assert len(requests) == 1


def test_owned_sessions_close_with_sdk_contexts():
    with Client("http://test") as client:
        assert not client._session.is_closed
    assert client._session.is_closed

    async def exercise():
        async with AsyncClient("http://test") as client:
            assert not client._session.is_closed
        assert client._session.is_closed

    asyncio.run(exercise())


def test_client_escapes_path_parameters():
    arguments = request_arguments("delete_server", {"server_id": "one/two?other=yes", "X-CHIV2-SERVER-BROWSER-KEY": "key"}, UNSET)
    assert arguments["url"] == "/api/v1/servers/one%2Ftwo%3Fother%3Dyes"


def test_request_preparation_preserves_configured_headers():
    defaults = httpx.Headers({"content-type": "text/plain", "x-trace": "original"})
    arguments = request_arguments(
        "login", {}, LoginRequest(token="test"),
        base_url="http://example.test/prefix", default_headers=defaults,
    )
    assert arguments["url"] == "http://example.test/prefix/api/v1/auth/login"
    assert arguments["headers"]["content-type"] == "application/json"
    assert arguments["headers"]["x-trace"] == "original"
    arguments["headers"]["x-trace"] = "changed"
    assert defaults == httpx.Headers({"content-type": "text/plain", "x-trace": "original"})


@pytest.mark.parametrize("asynchronous", [False, True])
def test_client_per_request_headers_do_not_leak_to_later_calls(asynchronous):
    requests = []

    def reply(request):
        requests.append(request)
        return httpx.Response(200, json={"banned_ips": []})

    async def exercise():
        transport = httpx.MockTransport(reply)
        session = httpx.AsyncClient(transport=transport) if asynchronous else httpx.Client(transport=transport)
        sdk_type = AsyncClient if asynchronous else Client
        sdk = sdk_type(
            "http://example.test/prefix/", session=session, timeout=3.0,
            headers={"x-chiv2-server-browser-admin-key": "configured"},
        )
        try:
            for parameters in ({"x_chiv2_server_browser_admin_key": "override"}, {}):
                result = sdk.get_ban_list(**parameters)
                result = await result if inspect.isawaitable(result) else result
                assert result.status == 200
        finally:
            if asynchronous:
                await session.aclose()
            else:
                session.close()

    asyncio.run(exercise())
    assert [request.headers["x-chiv2-server-browser-admin-key"] for request in requests] == ["override", "configured"]
    assert all(str(request.url) == "http://example.test/prefix/api/v1/admin/ban-list" for request in requests)
    assert all(request.extensions["timeout"] == {"connect": 3.0, "read": 3.0, "write": 3.0, "pool": 3.0} for request in requests)


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("operation", ["get_ban_list", "delete_server"])
@pytest.mark.parametrize("destination", ["https://attacker.test/collect", "http://example.test/collect", "https://example.test/other"])
def test_client_never_forwards_credentials_on_redirect(asynchronous, operation, destination):
    requests = []

    def reply(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(307, headers={"Location": destination})
        return httpx.Response(200, json={"status": "ok", "message": "ok", "banned_ips": []})

    async def exercise():
        transport = httpx.MockTransport(reply)
        session = (httpx.AsyncClient if asynchronous else httpx.Client)(transport=transport, follow_redirects=True)
        sdk = (AsyncClient if asynchronous else Client)("https://example.test", session=session)
        parameters = (
            {"x_chiv2_server_browser_admin_key": "admin-sentinel"}
            if operation == "get_ban_list"
            else {"server_id": "server", "x_chiv2_server_browser_key": "server-sentinel"}
        )
        try:
            response = getattr(sdk, operation)(**parameters)
            response = await response if inspect.isawaitable(response) else response
            assert response.status == 307
            assert response.headers["Location"] == destination
        finally:
            if asynchronous:
                await session.aclose()
            else:
                session.close()

    asyncio.run(exercise())
    assert len(requests) == 1
    credential_header = "x-chiv2-server-browser-admin-key" if operation == "get_ban_list" else "x-chiv2-server-browser-key"
    assert credential_header in requests[0].headers
