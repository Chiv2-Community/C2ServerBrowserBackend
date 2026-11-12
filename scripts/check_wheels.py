"""Smoke-test both built wheels outside the source checkout."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE = '''
import sys
from importlib.resources import files
from server_browser_api.models import LoginRequest
from server_browser_api.apis.api_v1_api_base import BaseApiV1Api
assert LoginRequest.from_json({"token": "example"}).token == "example"
assert not any(name.startswith("server_browser_backend") for name in sys.modules)
assert files("server_browser_api").joinpath("py.typed").is_file()
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
    print("Both wheels work under Uvicorn outside the checkout; generated API imports independently.")
finally:
    server.should_exit = True
    thread.join(timeout=10)
    assert not thread.is_alive(), "Uvicorn failed to shut down"
    for listener in sockets:
        listener.close()
'''


def main() -> None:
    wheels = sorted((ROOT / "dist").glob("*.whl"))
    if len(wheels) != 2:
        raise SystemExit("Build both packages and retain only their current wheels in dist/.")
    with tempfile.TemporaryDirectory(prefix="server-browser-wheel-smoke-") as temporary:
        directory = Path(temporary)
        environment = directory / "venv"
        subprocess.run(["uv", "venv", str(environment)], check=True)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(["uv", "pip", "install", "--python", str(python), *map(str, wheels)], check=True)
        # Do not inherit a source PYTHONPATH or use the repository as cwd.
        clean_environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        subprocess.run([str(python), "-I", "-c", SMOKE], cwd=directory, env=clean_environment, check=True)


if __name__ == "__main__":
    main()
