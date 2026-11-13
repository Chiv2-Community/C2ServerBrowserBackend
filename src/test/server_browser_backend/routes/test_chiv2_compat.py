from ipaddress import ip_address

import pytest
from fastapi.testclient import TestClient

from server_browser_backend.routes import chiv2_compat
from . import prepare_test_state

test_ports = {"game": 1234, "ping": 1235, "a2s": 1236}

test_server_json = {
    "name": "Test Server",
    "description": "Test Description",
    "ports": test_ports,
    "player_count": 0,
    "max_players": 100,
    "current_map": "Test Map",
}


def test_get_servers(client: TestClient):
    source_ip = "42.0.69.0"
    local_ip = "192.168.1.24"

    response = client.post("/api/tbio/GetCurrentGames")
    assert response.status_code == 200
    assert len(response.json()["Data"]["Games"]) == 0

    post_response_1 = client.post(
        "/api/v1/servers",
        json={**test_server_json, "local_ip_address": local_ip},
        headers={"X-Forwarded-For": source_ip}
    )

    assert post_response_1.status_code == 201, post_response_1.json()

    garbage_ip = "66.6.77.7"
    post_response_2 = client.post(
        "/api/v1/servers",
        json={
            **test_server_json,
            "name": "Test Server 2",
            "password_protected": True,
        }, headers={"X-Forwarded-For": garbage_ip}
    )

    assert post_response_2.status_code == 201, post_response_2.json()

    response = client.post("/api/tbio/GetCurrentGames", headers={"X-Forwarded-For": source_ip})
    assert response.status_code == 200
    assert len(response.json()["Data"]["Games"]) == 2

    # assert one is password protected and one isn't (Games.Tags.pp_b)
    assert response.json()["Data"]["Games"][0]["Tags"]["pp_b"] != response.json()["Data"]["Games"][1]["Tags"]["pp_b"]

    # Only the source-matching server uses its local address.
    assert response.json()["Data"]["Games"][0]["ServerIPV4Address"] == local_ip
    assert response.json()["Data"]["Games"][1]["ServerIPV4Address"] == garbage_ip

    listing = client.get("/api/v1/servers", headers={"X-Forwarded-For": source_ip})
    assert listing.status_code == 200
    listed_server = listing.json()["servers"][0]
    assert "ip_address" not in listed_server
    assert "local_ip_address" not in listed_server


def test_get_servers_can_expose_registered_ips_for_diagnostics(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    source_ip = "42.0.69.0"
    local_ip = "192.168.1.24"
    response = client.post(
        "/api/v1/servers",
        json={**test_server_json, "local_ip_address": local_ip},
        headers={"X-Forwarded-For": source_ip},
    )
    assert response.status_code == 201

    monkeypatch.setenv("EXPOSE_REGISTERED_IPS", "1")
    listing = client.get("/api/v1/servers", headers={"X-Forwarded-For": source_ip})
    listed_server = listing.json()["servers"][0]
    assert listed_server["ip_address"] == source_ip
    assert listed_server["local_ip_address"] == local_ip

@pytest.mark.parametrize("bracketed", [False, True])
def test_get_servers_ipv6_uses_bracketed_legacy_address_fields(client: TestClient, bracketed: bool):
    source_ip = "42.0.69.0"
    ipv6 = "2a0c:d242:903b:ba00::ff99"
    response = client.post(
        "/api/v1/servers",
        json={
            **test_server_json,
            "name": "IPv6 Server",
            "description": "IPv6 test",
            "max_players": 64,
            "local_ip_address": f"[{ipv6}]" if bracketed else ipv6,
        },
        headers={"X-Forwarded-For": source_ip},
    )
    assert response.status_code == 201

    response = client.post("/api/tbio/GetCurrentGames", headers={"X-Forwarded-For": source_ip})
    game = response.json()["Data"]["Games"][0]
    assert game["ServerHostname"] == f"[{ipv6}]"
    assert game["ServerIPV4Address"] == f"[{ipv6}]"


def test_ipv6_local_address_is_source_matching_local_client_override(client: TestClient):
    source_ip = "42.0.69.0"
    local_ipv6 = "2a0c:d242:903b:ba00::ff99"
    response = client.post(
        "/api/v1/servers",
        json={
            **test_server_json,
            "name": "Remote IPv6 Selection",
            "description": "IPv6 selection test",
            "max_players": 64,
            "local_ip_address": local_ipv6,
        },
        headers={"X-Forwarded-For": source_ip},
    )
    assert response.status_code == 201

    response = client.post(
        "/api/tbio/GetCurrentGames",
        headers={"X-Forwarded-For": "42.0.69.1"},
    )
    game = response.json()["Data"]["Games"][0]
    assert game["ServerHostname"] == source_ip


@pytest.mark.parametrize("joining_locally", [False, True])
@pytest.mark.parametrize(
    "public_ip, client_ip, local_ip",
    [
        ("192.0.2.1", "192.0.2.1", "192.168.1.1"),
        ("2001:db8::1", "2001:0db8:0:0:0:0:0:1", "fd00::1"),
    ],
)
def test_compat_serializes_parsed_ips(client: TestClient, browser, joining_locally, public_ip, client_ip, local_ip):
    registration = client.post(
        "/api/v1/servers",
        json={**test_server_json, "local_ip_address": local_ip},
        headers={"X-Forwarded-For": public_ip},
    )
    assert registration.status_code == 201
    server_id = registration.json()["server"]["unique_id"]
    server = browser.server_list.get(server_id)
    assert server is not None
    assert server.ip_address == ip_address(public_ip)
    assert server.local_ip_address == ip_address(local_ip)
    headers = {"X-Forwarded-For": client_ip if joining_locally else "192.0.2.2"}
    expected = local_ip if joining_locally else public_ip

    games = client.post("/api/tbio/GetCurrentGames", headers=headers)
    assert games.status_code == 200
    game = games.json()["Data"]["Games"][0]
    legacy_address = f"[{expected}]" if ip_address(expected).version == 6 else expected
    assert game["ServerHostname"] == legacy_address
    assert game["ServerIPV4Address"] == legacy_address

    match = client.post(
        "/api/playfab/Client/Matchmake", json={"LobbyId": server_id}, headers=headers
    )
    assert match.status_code == 200
    assert match.json()["data"]["ServerHostname"] == expected


def test_tbio_parses_client_ip_once_per_listing(client: TestClient, monkeypatch):
    source_ip = "2001:db8::1"
    for name in ("First", "Second"):
        registration = client.post(
            "/api/v1/servers",
            json={**test_server_json, "name": name, "local_ip_address": "fd00::1"},
            headers={"X-Forwarded-For": source_ip},
        )
        assert registration.status_code == 201

    parsed_inputs = []

    def parse_client_ip(address):
        parsed_inputs.append(address)
        return ip_address(address)

    monkeypatch.setattr(chiv2_compat, "parse_ip_address", parse_client_ip)
    response = client.post(
        "/api/tbio/GetCurrentGames", headers={"X-Forwarded-For": source_ip}
    )
    assert response.status_code == 200
    games = response.json()["Data"]["Games"]
    assert len(games) == 2
    assert all(game["ServerHostname"] == "[fd00::1]" for game in games)
    assert parsed_inputs == [source_ip]


@pytest.mark.parametrize("body,banned,expected_motd", [
    pytest.param({"Language": "test"}, False, "test", id="translated"),
    pytest.param({"Language": "test"}, True, "test banned", id="banned-translated"),
    pytest.param({}, True, "This address is banned. Ensure your VPN is disabled. Contact an admin for more information.", id="banned-default"),
    pytest.param({}, False, None, id="default"),
    pytest.param({"Language": "not_supported"}, False, None, id="fallback"),
])
def test_motd_endpoint(client: TestClient, browser, admin_key, body, banned, expected_motd):
    if banned:
        prepare_test_state(browser, admin_key, ban_list=["127.0.0.1"])
    response = client.post("/api/tbio/GetMotd", json=body)
    assert response.status_code == 200
    if expected_motd is not None:
        assert response.json()["Data"]["Motd"] == expected_motd


def test_client_matchmake_2(client: TestClient):
    ip_address = "42.0.69.42"
    
    registration_response = client.post(
        "/api/v1/servers",
        json={**test_server_json, "local_ip_address": "192.168.1.2"},
        headers={"X-Forwarded-For": ip_address},
    )

    unique_id = registration_response.json()["server"]["unique_id"]

    response = client.post("/api/playfab/Client/Matchmake", json={"LobbyId": unique_id})
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["data"]["ServerHostname"] == ip_address
    assert response_json["data"]["ServerPort"] == 1234

def test_local_client_matchmake(client: TestClient):
    ip_address = "42.0.69.42"
    local_ip_address = "192.168.1.4"
    
    registration_response = client.post(
        "/api/v1/servers",
        json={**test_server_json, "local_ip_address": local_ip_address},
        headers={"X-Forwarded-For": ip_address},
    )

    unique_id = registration_response.json()["server"]["unique_id"]

    response = client.post("/api/playfab/Client/Matchmake", json={"LobbyId": unique_id}, headers={"X-Forwarded-For": ip_address})
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["data"]["ServerHostname"] == local_ip_address
    assert response_json["data"]["ServerPort"] == 1234

def test_motd_no_json(client: TestClient):
    response = client.post("/api/tbio/GetMotd", headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert response.json()["status"] == "missing_json_body"

def test_matchmake_no_json(client: TestClient):
    response = client.post("/api/playfab/Client/Matchmake", headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert response.json()["status"] == "missing_json_body"
