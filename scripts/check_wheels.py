"""Rebuild all sdists and verify wheel dependency boundaries outside the checkout."""
from __future__ import annotations

import os
import json
import subprocess
import tempfile
from zipfile import ZipFile
from pathlib import Path
import tarfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
SMOKE = '''
import sys
from importlib.resources import files
from server_browser_models.models import LoginRequest
from server_browser_server.apis.api_v1_api_base import BaseApiV1Api
assert LoginRequest.from_json({"token": "example"}).token == "example"
assert not any(name.startswith("server_browser_backend") for name in sys.modules)
assert files("server_browser_models").joinpath("py.typed").is_file()
from server_browser_backend.main import app
import json
import socket
import threading
import time
from urllib.request import Request, ProxyHandler, build_opener
import uvicorn

listener = socket.socket()
listener.bind(("127.0.0.1", 0))
sockets = [listener]
ipv6 = None
try:
    ipv6 = socket.socket(socket.AF_INET6)
    ipv6.bind(("::1", 0))
    sockets.append(ipv6)
except OSError:
    if ipv6 is not None:
        ipv6.close()
    ipv6 = None
    print("IPv6 loopback unavailable; IPv6 socket smoke skipped.")
server = uvicorn.Server(uvicorn.Config(app, log_level="warning", proxy_headers=False))
thread = threading.Thread(target=server.run, kwargs={"sockets": sockets}, daemon=True)
thread.start()
try:
    deadline = time.monotonic() + 10
    while not server.started:
        assert thread.is_alive() and time.monotonic() < deadline, "Uvicorn failed to start"
        time.sleep(0.01)
    base = "http://127.0.0.1:" + str(listener.getsockname()[1])
    import asyncio
    import httpx
    from server_browser_client import Client, AsyncClient
    from server_browser_models.models import ServerListResponse
    with httpx.Client(trust_env=False) as transport, Client(base, session=transport) as sdk:
        result = sdk.get_servers()
        assert result.status == 200 and isinstance(result.body, ServerListResponse)
    async def exercise_client():
        async with httpx.AsyncClient(trust_env=False) as transport, AsyncClient(base, session=transport) as sdk:
            result = await sdk.get_servers()
            assert result.status == 200 and isinstance(result.body, ServerListResponse)
    asyncio.run(exercise_client())
    opener = build_opener(ProxyHandler({}))
    def request(path, body=None, method="GET"):
        data = None if body is None else json.dumps(body).encode()
        return opener.open(Request(base + path, data=data, method=method, headers={"Content-Type": "application/json"}), timeout=5)
    assert request("/api/v1/auth/jwks.json").status == 200
    spec = request("/api/v1/swagger.yaml")
    assert spec.status == 200 and b"openapi:" in spec.read()
    motd = request("/api/tbio/GetMotd", {}, "POST")
    assert motd.status == 200 and json.load(motd)["Success"] is True
    registration = request("/api/v1/servers", {
        "name": "wheel smoke", "description": "", "current_map": "Test",
        "player_count": 0, "max_players": 32,
        "ports": {"game": 7777, "ping": 7778, "a2s": 7779},
    }, "POST")
    assert registration.status == 201
    assert "ip_address" not in json.load(registration)["server"]
    assert request("/api/tbio/GetCurrentGames", method="POST").status == 200
    if ipv6 is not None:
        base = "http://[::1]:" + str(ipv6.getsockname()[1])
        registration = request("/api/v1/servers", {
            "name": "IPv6 wheel smoke", "description": "", "current_map": "Test",
            "player_count": 0, "max_players": 32, "local_ip_address": "[fd00::1]",
            "ports": {"game": 7777, "ping": 7778, "a2s": 7779},
        }, "POST")
        assert registration.status == 201
        server_id = json.load(registration)["server"]["unique_id"]
        games = json.load(request("/api/tbio/GetCurrentGames", method="POST"))["Data"]["Games"]
        assert games[-1]["ServerHostname"] == "[fd00::1]"
        assert games[-1]["ServerIPV4Address"] == "[fd00::1]"
        match = json.load(request("/api/playfab/Client/Matchmake", {"LobbyId": server_id}, "POST"))
        assert match["data"]["ServerHostname"] == "fd00::1"
        print("IPv6 loopback, bracketed registration, TBIO brackets, and raw PlayFab IP passed.")
    print("Backend wheels work under Uvicorn outside the checkout.")
finally:
    server.should_exit = True
    thread.join(timeout=10)
    assert not thread.is_alive(), "Uvicorn failed to shut down"
    for listener in sockets:
        listener.close()
'''


def check_contract(wheel: Path, expected: dict) -> None:
    with ZipFile(wheel) as archive:
        assert json.loads(archive.read("server_browser_models/contract.json")) == expected
        assert yaml.safe_load(archive.read("server_browser_models/openapi.yaml")) == expected


def main() -> None:
    names = ["server_browser_models", "server_browser_server", "server_browser_fastapi", "server_browser_client", "chivalry2_unofficial_server_browser_backend"]
    wheels = {}
    sdists = {}
    for name in names:
        candidates = list((ROOT / "dist").glob(f"{name}-*.whl"))
        sources = list((ROOT / "dist").glob(f"{name}-*.tar.gz"))
        if len(candidates) != 1 or len(sources) != 1:
            raise SystemExit(f"Retain exactly one current wheel and sdist for {name} in dist/.")
        wheels[name] = candidates[0]
        sdists[name] = sources[0]
    expected = yaml.safe_load((ROOT / "assets/chiv2-server-browser-api.yaml").read_text())
    check_contract(wheels["server_browser_models"], expected)
    with tempfile.TemporaryDirectory(prefix="server-browser-wheel-smoke-") as temporary:
        directory = Path(temporary)
        api_sdist = sdists["server_browser_models"]
        with tarfile.open(api_sdist) as archive:
            names = archive.getnames()
            assert any(name.endswith("/assets/chiv2-server-browser-api.yaml") for name in names)
            assert not any(name.endswith(("/server_browser_models/contract.json", "/server_browser_models/openapi.yaml")) for name in names)
        rebuilt = directory / "rebuilt"
        for sdist in sdists.values():
            subprocess.run(["uv", "build", "--wheel", str(sdist), "--out-dir", str(rebuilt)], cwd=directory, check=True)
        rebuilt_wheels = {name: next(rebuilt.glob(f"{name}-*.whl")) for name in wheels}
        check_contract(rebuilt_wheels["server_browser_models"], expected)
        clean_environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        for package in ("models", "server", "client", "fastapi"):
            isolated = directory / package
            subprocess.run(["uv", "venv", str(isolated)], check=True)
            executable = isolated / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            dependencies = ["models"] + (["server"] if package == "fastapi" else []) + ([] if package == "models" else [package])
            subprocess.run(["uv", "pip", "install", "--python", str(executable), *[str(rebuilt_wheels[f"server_browser_{name}"]) for name in dependencies]], check=True)
            probe = f'''
from importlib.util import find_spec
from importlib.resources import files
import server_browser_{package}
from server_browser_models.models import LoginRequest
assert LoginRequest.from_json({{"token": "test"}}).token == "test"
assert files("server_browser_{package}").joinpath("py.typed").is_file()
assert find_spec("server_browser_backend") is None
assert find_spec("uvicorn") is None
'''
            if package != "fastapi":
                probe += 'assert find_spec("fastapi") is None\nassert find_spec("starlette") is None\n'
            if package in ("models", "server"):
                probe += 'assert find_spec("httpx") is None\n'
            if package == "server":
                probe += '''
from server_browser_server.apis.api_v1_api_base import BaseApiV1Api
from server_browser_server.apis.chiv2_compat_api_base import BaseChiv2CompatApi
from server_browser_server import ApiResponse, RequestContext
from server_browser_models.models import TbioServerListResponse, TbioServerListData, TbioMotdResponse, PlayfabErrorResponse
assert RequestContext("192.0.2.1").client_ip == "192.0.2.1"
assert BaseApiV1Api.__abstractmethods__ and BaseChiv2CompatApi.__abstractmethods__
class Implementation(BaseChiv2CompatApi):
    def tbio_get_servers(self, request):
        return ApiResponse(TbioServerListResponse(success=True, data=TbioServerListData(game_count=0, player_count=0, games=[])))
    def get_motd(self, request, *, motd_request):
        return ApiResponse(TbioMotdResponse(success=True, data={}, expiration=1))
    def playfab_client_matchmake(self, request, *, matchmake_request):
        return ApiResponse(PlayfabErrorResponse(code=404, data={}, message="not found", params={}, success=False), 404)
assert Implementation().tbio_get_servers(RequestContext("192.0.2.1")).body.data.games == []
'''
            subprocess.run([str(executable), "-I", "-c", probe], cwd=directory, env=clean_environment, check=True)
        environment = directory / "venv"
        subprocess.run(["uv", "venv", str(environment)], check=True)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(["uv", "pip", "install", "--python", str(python), *map(str, rebuilt_wheels.values())], check=True)
        # Do not inherit a source PYTHONPATH or use the repository as cwd.
        clean_environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        subprocess.run([str(python), "-I", "-c", SMOKE], cwd=directory, env=clean_environment, check=True)


if __name__ == "__main__":
    main()
