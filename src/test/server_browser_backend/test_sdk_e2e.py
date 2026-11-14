"""Generated clients against real Python handlers, persistence and HTTP sockets."""

import asyncio
import errno
import inspect
import json
import os
import re
import socket
import subprocess
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn
import yaml
from openapi_schema_validator import OAS30Validator

from server_browser_client import AsyncClient, Client
from server_browser_models import models
from server_browser_models.runtime import contract
from server_browser_backend.auth.signing import SigningKeys, provision

ROOT = Path(__file__).resolve().parents[3]


def operations():
    return {
        (method.upper(), path): operation
        for path, entry in contract()["paths"].items()
        for method, operation in entry.items()
        if method in {"get", "post", "put", "delete", "patch", "head", "options"}
    }


class RecordedServer:
    def __init__(self, app, host, diagnostic):
        self.app, self.host, self.diagnostic = app, host, diagnostic
        self.exchanges = []

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        messages = []

        async def record(message):
            messages.append(message.copy())
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                # Publish before the client can finish reading the final bytes.
                self.exchanges.append((scope["method"], scope["path"], messages))
            await send(message)

        await self.app(scope, receive, record)

    def assert_contract_and_operation_coverage(self):
        covered = set()
        for method, path, messages in self.exchanges:
            matches = [
                operation for (verb, template), operation in operations().items()
                if verb == method and re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", template), path)
            ]
            assert len(matches) == 1, (method, path)
            operation = matches[0]
            covered.add(operation["operationId"])
            start = next(message for message in messages if message["type"] == "http.response.start")
            body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
            declaration = operation["responses"].get(str(start["status"]), operation["responses"].get("default"))
            assert declaration is not None
            media_type = dict(start["headers"])[b"content-type"].decode().split(";")[0]
            schema = declaration["content"][media_type]["schema"]
            if media_type == "application/json":
                OAS30Validator({"components": contract()["components"], **schema}).validate(json.loads(body))
            else:
                assert schema["type"] == "string"
                assert yaml.safe_load(body) == contract()
        assert covered == {operation["operationId"] for operation in operations().values()}


@pytest.fixture(params=["127.0.0.1", "::1"])
def host(request):
    return request.param


@pytest.fixture(params=[False, True], ids=["ordinary", "diagnostic"])
def live_server(request, host, app_factory, tmp_path):
    keyring = tmp_path / "signing.json"
    provision(keyring)
    app = app_factory(signing_keys=SigningKeys(keyring), expose_ips=lambda: request.param,
                      debug_mode=False, trusted_proxies=())
    recorded = RecordedServer(app, host, request.param)
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family) as listener:
        try:
            listener.bind((host, 0))
        except OSError as error:
            if family == socket.AF_INET6 and error.errno in {errno.EAFNOSUPPORT, errno.EADDRNOTAVAIL, errno.EPROTONOSUPPORT}:
                pytest.skip("IPv6 loopback unavailable")
            raise
        listener.listen()
        address = f"[{host}]" if family == socket.AF_INET6 else host
        recorded.url = f"http://{address}:{listener.getsockname()[1]}"
        server = uvicorn.Server(uvicorn.Config(recorded, log_level="warning", access_log=False, proxy_headers=False))
        worker = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                assert worker.is_alive() and time.monotonic() < deadline, "Uvicorn failed to start"
                time.sleep(0.01)
            yield recorded
        finally:
            server.should_exit = True
            worker.join(timeout=10)
            assert not worker.is_alive(), "Uvicorn failed to stop"


async def exercise_python(client, server, admin_key):
    async def call(operation, model, status=200, **parameters):
        response = getattr(client, operation)(**parameters)
        if inspect.isawaitable(response):
            response = await response
        assert response.status == status, operation
        assert isinstance(response.body, model), operation
        return response.body

    admin = {"x_chiv2_server_browser_admin_key": admin_key}
    assert (await call("jwks", models.JwksResponse)).keys
    assert yaml.safe_load(await call("send_swagger", str)) == contract()
    assert (await call("login", models.StatusResponse, 410, login_request=models.LoginRequest(token="retired"))).status == "auth_retired"
    assert not (await call("get_servers", models.ServerListResponse)).servers
    registration_request = models.ServerRegistrationRequest.from_json({
        "name": "SDK café 🛡", "description": "wire round trip", "current_map": "map",
        "player_count": 1, "max_players": 32, "ports": {"game": 7777, "ping": 7778, "a2s": 7779},
    })
    registration = await call("register", models.RegistrationResponse, 201, server_registration_request=registration_request)
    assert registration.server.name == registration_request.name
    assert "ip_address" not in registration.server.model_dump()
    credentials = {"server_id": registration.server.unique_id, "x_chiv2_server_browser_key": registration.key}
    await call("register", models.StatusResponse, 400, server_registration_request=registration_request.model_copy(update={"player_count": 1025}))
    await call("heartbeat", models.StatusResponse, 400, server_id=credentials["server_id"])
    await call("heartbeat", models.StatusResponse, 403, **{**credentials, "x_chiv2_server_browser_key": "wrong"})
    await call("heartbeat", models.UpdateResponse, **credentials)
    await call("update", models.UpdateResponse, **credentials, update_registered_server=models.UpdateRegisteredServer(player_count=2, max_players=32, current_map="next"))
    entry = (await call("get_servers", models.ServerListResponse)).servers[0]
    assert entry.current_map == "next" and entry.player_count == 2
    assert isinstance(entry, models.ServerResponseWithIP) == server.diagnostic
    if server.diagnostic:
        assert str(entry.ip_address) == server.host and entry.local_ip_address is None
    else:
        assert "ip_address" not in entry.model_dump()

    await call("get_ban_list", models.StatusResponse, 403)
    await call("get_verified_list", models.StatusResponse, 403, x_chiv2_server_browser_admin_key="wrong")
    assert not (await call("get_ban_list", models.BanListResponse, **admin)).banned_ips
    bans = models.IpListRequest(banned_ips=["203.0.113.0/24", "2001:db8::/32"])
    assert len((await call("add_to_ban_list", models.BanListResponse, **admin, ip_list_request=bans)).banned_ips) == 2
    for ip in ("203.0.113.4", "2001:db8::4"):
        assert (await call("check_banned", models.BanStatusResponse, ip=ip)).banned
    assert not (await call("remove_from_ban_list", models.BanListResponse, **admin, ip_list_request=bans)).banned_ips
    assert not (await call("check_banned", models.BanStatusResponse, ip="2001:db8::4")).banned
    verified = models.IpListRequest(verified_ips=[server.host])
    await call("get_verified_list", models.VerifiedListResponse, **admin)
    await call("add_to_verified_list", models.VerifiedListResponse, **admin, ip_list_request=verified)
    assert (await call("get_servers", models.ServerListResponse)).servers[0].is_verified
    await call("remove_from_verified_list", models.VerifiedListResponse, **admin, ip_list_request=verified)
    assert not (await call("get_servers", models.ServerListResponse)).servers[0].is_verified

    games = await call("tbio_get_servers", models.TbioServerListResponse)
    assert games.success and games.data.games[0].lobby_id == credentials["server_id"]
    assert (await call("get_motd", models.TbioMotdResponse, motd_request=models.MotdRequest(language="en"))).success
    match = await call("playfab_client_matchmake", models.PlayfabMatchmakeResponse, matchmake_request=models.MatchmakeRequest(lobby_id=credentials["server_id"]))
    assert str(match.data.server_hostname) == server.host

    advertised = await call("register", models.RegistrationResponse, 201, server_registration_request=registration_request.model_copy(update={
        "local_ip_address": "[fd00::5]", "password_protected": True,
        "mods": [models.Mod(name="mod", organization="org", version="1", active=True)],
    }))
    assert advertised.server.password_protected and advertised.server.mods[0].active
    entries = (await call("get_servers", models.ServerListResponse)).servers
    advertised_entry = next(entry for entry in entries if entry.unique_id == advertised.server.unique_id)
    if server.diagnostic:
        assert str(advertised_entry.local_ip_address) == "fd00::5"
    games = await call("tbio_get_servers", models.TbioServerListResponse)
    game = next(game for game in games.data.games if game.lobby_id == advertised.server.unique_id)
    assert str(game.server_hostname) == "fd00::5"
    assert game.model_dump(mode="json", by_alias=True)["ServerHostname"] == "[fd00::5]"
    matched = await call("playfab_client_matchmake", models.PlayfabMatchmakeResponse, matchmake_request=models.MatchmakeRequest(lobby_id=advertised.server.unique_id))
    assert str(matched.data.server_hostname) == "fd00::5"
    await call("delete_server", models.StatusResponse, server_id=advertised.server.unique_id, x_chiv2_server_browser_key=advertised.key)
    await call("delete_server", models.StatusResponse, **credentials)
    assert not (await call("get_servers", models.ServerListResponse)).servers
    await call("heartbeat", models.StatusResponse, 404, **credentials)
    await call("delete_server", models.StatusResponse, 404, **credentials)
    missing = await call("playfab_client_matchmake", models.PlayfabErrorResponse, 404, matchmake_request=models.MatchmakeRequest(lobby_id=credentials["server_id"]))
    assert missing.code == 404 and not missing.success


@pytest.mark.parametrize("asynchronous", [False, True], ids=["python-sync", "python-async"])
def test_python_clients_against_python_server(live_server, admin_key, asynchronous):
    async def run():
        if asynchronous:
            async with httpx.AsyncClient(trust_env=False) as transport, AsyncClient(live_server.url, session=transport) as client:
                await exercise_python(client, live_server, admin_key)
        else:
            with httpx.Client(trust_env=False) as transport, Client(live_server.url, session=transport) as client:
                await exercise_python(client, live_server, admin_key)

    asyncio.run(run())
    live_server.assert_contract_and_operation_coverage()


@pytest.fixture(scope="session", params=["server-browser-client", "server-browser-client-sdk"])
def rust_e2e_executable(request):
    result = subprocess.run([
        "cargo", "test", "--locked", "--manifest-path", str(ROOT / "sdk/rust/Cargo.toml"),
        "-p", request.param, "--test", "end_to_end", "--no-run", "--message-format=json",
    ], cwd=ROOT, capture_output=True, text=True, check=True, timeout=300)
    executables = [message["executable"] for line in result.stdout.splitlines()
                   if (message := json.loads(line)).get("reason") == "compiler-artifact" and message.get("executable")]
    assert len(executables) == 1
    return request.param, executables[0]


def test_rust_client_against_python_server(rust_e2e_executable, live_server, admin_key):
    package, executable = rust_e2e_executable
    test = "generated_client_against_python_backend" if package == "server-browser-client" else "registration_sdk_against_python_backend"
    subprocess.run([executable, "--ignored", "--exact", test],
                   env={**os.environ, "SDK_E2E_URL": live_server.url, "SDK_E2E_ADMIN_KEY": admin_key,
                        "SDK_E2E_HOST": live_server.host, "SDK_E2E_DIAGNOSTIC": str(live_server.diagnostic)},
                   check=True, timeout=30)
    if package == "server-browser-client":
        live_server.assert_contract_and_operation_coverage()
