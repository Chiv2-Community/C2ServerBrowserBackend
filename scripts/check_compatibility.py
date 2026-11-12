"""Replay deterministic HTTP/state sequences against the pre-migration baseline.

Requires git, uv, and access to install the baseline's dependencies. Never modifies
the baseline checkout or operator configuration. This is bounded regression
evidence, not proof of equivalence for every possible input.
"""
from __future__ import annotations

import difflib
from copy import deepcopy
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "80e1fae0e635d6ae1619ab75ea87a9add50749ef"
PROBE = r'''
import dataclasses
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch
from cryptography.hazmat.primitives import serialization

from server_browser_backend.main import app
from server_browser_backend.routes import shared, api_v1, chiv2_compat
import server_browser_backend.server_list as registry

class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 12, 12, 0, 0, tzinfo=tz)

api_v1.datetime = chiv2_compat.datetime = registry.datetime = Clock
api_v1.uuid4 = lambda: "registration-id"
chiv2_compat.uuid4 = lambda: "ticket-id"
registry.secrets.token_hex = lambda n: "fixed-secret"
shared.token_reissuer.private_key = serialization.load_pem_private_key(Path(os.environ["PROBE_KEY"]).read_bytes(), password=None)
shared.token_reissuer.public_key = shared.token_reissuer.private_key.public_key()

if sys.argv[1] == "flask":
    client = app.test_client()
    def request(method, path, **kwargs):
        response = client.open(path, method=method, **kwargs)
        return response.status_code, response.content_type, response.get_json(silent=True), response.headers.get("Allow")
else:
    from fastapi.testclient import TestClient
    client = TestClient(app, client=("127.0.0.1", 1234), raise_server_exceptions=False)
    def request(method, path, **kwargs):
        if "data" in kwargs:
            kwargs["content"] = kwargs.pop("data")
        response = client.request(method, path, **kwargs)
        try:
            body = response.json()
        except ValueError:
            body = None
        return response.status_code, response.headers.get("content-type"), body, response.headers.get("allow")

def plain(value):
    if dataclasses.is_dataclass(value):
        return {field.name: plain(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if hasattr(value, "model_dump"):
        return plain(value.model_dump(by_alias=True))
    if isinstance(value, (IPv4Address, IPv6Address)):
        return str(value)
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain(item) for item in value]
    return value

records = {}
def record(name, method, path, **kwargs):
    code, media, body, allow = request(method, path, **kwargs)
    records[name] = {
        "status": code, "content_type": media, "body": body,
        "allow": sorted(item.strip() for item in allow.split(",")) if allow else None,
        "servers": plain(shared.server_list.get_all()),
        "files": {path.name: path.read_text() for path in sorted(Path(os.environ["CONFIG_DIR"]).glob("*.txt"))},
    }
    return body

registration = {
    "name": "Probe", "description": "", "current_map": "Map", "player_count": 2,
    "max_players": 32, "ports": {"game": 7777, "ping": 7778, "a2s": 7779},
}
key = {shared.KEY_HEADER: "fixed-secret"}
admin = {shared.ADMIN_KEY_HEADER: shared.ADMIN_KEY}
for family, ip in (("ipv4", "192.0.2.1"), ("ipv6", "2001:db8::1"), ("ipv6-bracketed", "2001:0db8:0:0:0:0:0:1")):
    shared.server_list.clear()
    source = {"X-Forwarded-For": ip}
    local_ip = "[fd00:0:0:0:0:0:0:1]" if family == "ipv6-bracketed" else "fd00::1"
    record(family + ":register", "POST", "/api/v1/servers", json={**registration, "local_ip_address": local_ip}, headers=source)
    for diagnostic in ("0", "1"):
        os.environ["EXPOSE_REGISTERED_IPS"] = diagnostic
        record(family + ":list:" + diagnostic, "GET", "/api/v1/servers")
    record(family + ":tbio", "POST", "/api/tbio/GetCurrentGames", headers=source)
    record(family + ":matchmake", "POST", "/api/playfab/Client/Matchmake", json={"LobbyId": "registration-id"}, headers=source)
    record(family + ":update", "PUT", "/api/v1/servers/registration-id", json={"current_map": "Next", "player_count": 3, "max_players": 32}, headers={**source, **key})
    record(family + ":heartbeat", "POST", "/api/v1/servers/registration-id/heartbeat", headers={**source, **key})
    record(family + ":missing-key", "POST", "/api/v1/servers/registration-id/heartbeat", headers=source)
    record(family + ":invalid-key", "DELETE", "/api/v1/servers/registration-id", headers={**source, shared.KEY_HEADER: "invalid"})
    record(family + ":changed-ip-invalid-key", "POST", "/api/v1/servers/registration-id/heartbeat", headers={shared.KEY_HEADER: "invalid"})
    record(family + ":changed-ip", "POST", "/api/v1/servers/registration-id/heartbeat", headers=key)
    record(family + ":missing-registration", "DELETE", "/api/v1/servers/registration-id", headers=key)

shared.server_list.clear()
record("defaults", "POST", "/api/v1/servers", json=registration)
record("delete", "DELETE", "/api/v1/servers/registration-id", headers=key)
record("missing-json", "POST", "/api/v1/servers")
record("head-list", "HEAD", "/api/v1/servers")
record("options-list", "OPTIONS", "/api/v1/servers")
for field, value in (("name", 3), ("mods", [1]), ("local_ip_address", None), ("password_protected", None)):
    record("invalid:" + field, "POST", "/api/v1/servers", json={**registration, field: value})
record("missing-field", "POST", "/api/v1/servers", json={key: value for key, value in registration.items() if key != "current_map"})
record("jwks", "GET", "/api/v1/auth/jwks.json")
with patch.object(shared.token_reissuer, "validate_and_reissue", return_value="fixed-token"):
    record("login", "POST", "/api/v1/auth/login", json={"token": "eos-token"})
record("motd", "POST", "/api/tbio/GetMotd", json={})
record("missing-lobby", "POST", "/api/playfab/Client/Matchmake", json={"LobbyId": "missing"})
for list_name, field in (("ban-list", "banned_ips"), ("verified-list", "verified_ips")):
    for method in ("PUT", "GET", "DELETE"):
        record(list_name + ":" + method, method, "/api/v1/admin/" + list_name, headers=admin, **({"json": {field: ["192.0.2.1"]}} if method != "GET" else {}))
    record(list_name + ":unauthorized", "GET", "/api/v1/admin/" + list_name)
record("banned-check", "GET", "/api/v1/check-banned/192.0.2.1")
shared.ban_list.add_all(shared.ADMIN_KEY, ["127.0.0.1"])
record("banned-before-body", "POST", "/api/v1/servers", json={})
record("banned-tbio", "POST", "/api/tbio/GetCurrentGames")
record("banned-motd", "POST", "/api/tbio/GetMotd", json={})
print(json.dumps(records, sort_keys=True))
'''


def main() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Fail even for the explicitly documented differences")
    strict = parser.parse_args().strict

    with tempfile.TemporaryDirectory(prefix="server-browser-compat-") as temporary:
        directory = Path(temporary)
        baseline = directory / "baseline"
        baseline.mkdir()
        archive = directory / "baseline.tar"
        subprocess.run(["git", "archive", BASELINE, "--output", str(archive)], cwd=ROOT, check=True)
        subprocess.run(["tar", "-xf", str(archive), "-C", str(baseline)], check=True)
        venv = directory / "venv"
        subprocess.run(["uv", "venv", str(venv)], check=True)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(["uv", "pip", "install", "--python", str(python), str(baseline)], check=True)
        key = directory / "key.pem"
        key.write_bytes(rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
        ))
        results = []
        for mode, interpreter, checkout in (("flask", python, baseline), ("fastapi", Path(sys.executable), ROOT)):
            config = directory / mode
            config.mkdir()
            for name in ("ban_list", "verified_list"):
                (config / f"{name}.txt").write_text("")
            environment = {**os.environ, "CONFIG_DIR": str(config), "ADMIN_KEY": "fixed-admin", "DEBUG_MODE": "false", "PROBE_KEY": str(key), "PYTHONPATH": str(checkout / "src")}
            process = subprocess.run([str(interpreter), "-c", PROBE, mode], cwd=checkout, env=environment, capture_output=True, text=True)
            if process.returncode:
                raise SystemExit(process.stderr)
            results.append(json.loads(process.stdout))
        old, new = results
        differences = []
        known_differences = []
        for name in sorted(old.keys() | new.keys()):
            expected = deepcopy(old.get(name))
            # Exact, narrow allowances. State/file/other response changes still fail.
            if not strict and name in {"ban-list:unauthorized", "verified-list:unauthorized"}:
                assert expected["status"] == 500
                assert expected["body"] == {"status": "error", "message": "An unexpected error occurred.", "context": None}
                expected["status"] = 403
                expected["body"] = {"status": "forbidden", "message": "Invalid admin key", "context": None}
            if not strict and name == "invalid:local_ip_address":
                assert expected["body"]["message"] == "Invalid type for key 'local_ip_address'. Got 'NoneType' with value 'None', but expected 'IPAddress'"
                expected["body"]["message"] = "Invalid type for key 'local_ip_address'. Got 'NoneType' with value 'None', but expected 'str'"
            if expected != new.get(name):
                differences.append(name)
                print("".join(difflib.unified_diff(
                    json.dumps(old.get(name), indent=2, sort_keys=True).splitlines(keepends=True),
                    json.dumps(new.get(name), indent=2, sort_keys=True).splitlines(keepends=True),
                    fromfile=f"baseline/{name}", tofile=f"fastapi/{name}",
                )))
            elif old.get(name) != new.get(name):
                known_differences.append(name)
        if differences:
            raise SystemExit(f"Compatibility differences: {', '.join(sorted(differences))}")
        print(f"{len(old) - len(known_differences)} deterministic HTTP/state cases match baseline {BASELINE}; {len(known_differences)} documented differences.")
        if known_differences:
            print("Documented differences: " + ", ".join(known_differences))


if __name__ == "__main__":
    main()
