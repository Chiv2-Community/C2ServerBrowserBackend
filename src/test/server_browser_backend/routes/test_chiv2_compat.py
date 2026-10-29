from datetime import datetime
from ipaddress import ip_address

import pytest
from flask.testing import FlaskClient

from server_browser_backend.main import app
from server_browser_backend.routes import chiv2_compat, shared
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


@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_get_servers(client: FlaskClient):
    prepare_test_state()

    source_ip = "42.0.69.0"
    local_ip = "192.168.1.24"

    response = client.post("/api/tbio/GetCurrentGames")
    assert response.status_code == 200
    assert len(response.get_json()["Data"]["Games"]) == 0

    post_response_1 = client.post(
        "/api/v1/servers",
        json={
            "name": "Test Server",
            "description": "Test Description",
            "ports": test_ports,
            "player_count": 0,
            "max_players": 100,
            "current_map": "Test Map",
            "local_ip_address": local_ip
        },
        headers={"X-Forwarded-For": source_ip}
    )

    assert post_response_1.status_code == 201, post_response_1.get_json()

    garbage_ip = "66.6.77.7"
    post_response_2 = client.post(
        "/api/v1/servers",
        json={
            "name": "Test Server 2",
            "description": "Test Description",
            "ports": test_ports,
            "player_count": 0,
            "max_players": 100,
            "current_map": "Test Map",
            "password_protected": True,
        }, headers={"X-Forwarded-For": garbage_ip}
    )

    assert post_response_2.status_code == 201, post_response_2.get_json()

    response = client.post("/api/tbio/GetCurrentGames", headers={"X-Forwarded-For": source_ip})
    assert response.status_code == 200
    assert len(response.get_json()["Data"]["Games"]) == 2

    # assert one is password protected and one isn't (Games.Tags.pp_b)
    assert response.get_json()["Data"]["Games"][0]["Tags"]["pp_b"] != response.get_json()["Data"]["Games"][1]["Tags"]["pp_b"]

    # asssert one sends the local ip and one sends the garbage ip
    assert response.get_json()["Data"]["Games"][0]["ServerIPV4Address"] == local_ip
    assert response.get_json()["Data"]["Games"][1]["ServerIPV4Address"] == garbage_ip

    listing = client.get("/api/v1/servers", headers={"X-Forwarded-For": source_ip})
    assert listing.status_code == 200
    listed_server = listing.get_json()["servers"][0]
    assert "ip_address" not in listed_server
    assert "local_ip_address" not in listed_server


def test_get_servers_can_expose_registered_ips_for_diagnostics(client: FlaskClient, monkeypatch: pytest.MonkeyPatch):
    prepare_test_state()
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
    listed_server = listing.get_json()["servers"][0]
    assert listed_server["ip_address"] == source_ip
    assert listed_server["local_ip_address"] == local_ip

@pytest.mark.parametrize("bracketed", [False, True])
def test_get_servers_ipv6_uses_bracketed_legacy_address_fields(client: FlaskClient, bracketed: bool):
    prepare_test_state()

    source_ip = "42.0.69.0"
    ipv6 = "2a0c:d242:903b:ba00::ff99"
    response = client.post(
        "/api/v1/servers",
        json={
            "name": "IPv6 Server",
            "description": "IPv6 test",
            "ports": test_ports,
            "player_count": 0,
            "max_players": 64,
            "current_map": "Test Map",
            "local_ip_address": f"[{ipv6}]" if bracketed else ipv6,
        },
        headers={"X-Forwarded-For": source_ip},
    )
    assert response.status_code == 201

    response = client.post("/api/tbio/GetCurrentGames", headers={"X-Forwarded-For": source_ip})
    game = response.get_json()["Data"]["Games"][0]
    assert game["ServerHostname"] == f"[{ipv6}]"
    assert game["ServerIPV4Address"] == f"[{ipv6}]"


def test_ipv6_local_address_is_source_matching_local_client_override(client: FlaskClient):
    prepare_test_state()

    source_ip = "42.0.69.0"
    local_ipv6 = "2a0c:d242:903b:ba00::ff99"
    response = client.post(
        "/api/v1/servers",
        json={
            "name": "Remote IPv6 Selection",
            "description": "IPv6 selection test",
            "ports": test_ports,
            "player_count": 0,
            "max_players": 64,
            "current_map": "Test Map",
            "local_ip_address": local_ipv6,
        },
        headers={"X-Forwarded-For": source_ip},
    )
    assert response.status_code == 201

    response = client.post(
        "/api/tbio/GetCurrentGames",
        headers={"X-Forwarded-For": "42.0.69.1"},
    )
    game = response.get_json()["Data"]["Games"][0]
    assert game["ServerHostname"] == source_ip


@pytest.mark.parametrize("joining_locally", [False, True])
@pytest.mark.parametrize(
    "public_ip, client_ip, local_ip",
    [
        ("192.0.2.1", "192.0.2.1", "192.168.1.1"),
        ("2001:db8::1", "2001:0db8:0:0:0:0:0:1", "fd00::1"),
    ],
)
def test_compat_serializes_parsed_ips(client: FlaskClient, joining_locally, public_ip, client_ip, local_ip):
    prepare_test_state()
    registration = client.post(
        "/api/v1/servers",
        json={**test_server_json, "local_ip_address": local_ip},
        headers={"X-Forwarded-For": public_ip},
    )
    assert registration.status_code == 201
    server_id = registration.get_json()["server"]["unique_id"]
    server = shared.server_list.get(server_id)
    assert server is not None
    assert server.ip_address == ip_address(public_ip)
    assert server.local_ip_address == ip_address(local_ip)
    headers = {"X-Forwarded-For": client_ip if joining_locally else "192.0.2.2"}
    expected = local_ip if joining_locally else public_ip

    games = client.post("/api/tbio/GetCurrentGames", headers=headers)
    assert games.status_code == 200
    game = games.get_json()["Data"]["Games"][0]
    legacy_address = f"[{expected}]" if ip_address(expected).version == 6 else expected
    assert game["ServerHostname"] == legacy_address
    assert game["ServerIPV4Address"] == legacy_address

    match = client.post(
        "/api/playfab/Client/Matchmake", json={"LobbyId": server_id}, headers=headers
    )
    assert match.status_code == 200
    assert match.get_json()["data"]["ServerHostname"] == expected


def test_tbio_parses_client_ip_once_per_listing(client: FlaskClient, monkeypatch):
    prepare_test_state()
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
    games = response.get_json()["Data"]["Games"]
    assert len(games) == 2
    assert all(game["ServerHostname"] == "[fd00::1]" for game in games)
    assert parsed_inputs == [source_ip]


def test_motd_endpoint(client: FlaskClient):
    prepare_test_state()

    response = client.post("/api/tbio/GetMotd", json={"Language": "test"})
    assert response.status_code == 200
    assert response.get_json()["Data"]["Motd"] == "test"

def test_banned_motd_endpoint(client: FlaskClient):
    prepare_test_state(ban_list=['127.0.0.1'])

    response = client.post("/api/tbio/GetMotd", json={"Language": "test"})
    assert response.status_code == 200
    assert response.get_json()["Data"]["Motd"] == "test banned"

def test_banned_default_motd_endpoint(client: FlaskClient):
    prepare_test_state(ban_list=['127.0.0.1'])

    response = client.post("/api/tbio/GetMotd", json={})
    assert response.status_code == 200
    assert response.get_json()["Data"]["Motd"] == "This address is banned. Ensure your VPN is disabled. Contact an admin for more information."


def test_motd_endpoint_default(client: FlaskClient):
    prepare_test_state()

    response = client.post("/api/tbio/GetMotd", json={})
    assert response.status_code == 200


def test_motd_endpoint_fallback(client: FlaskClient):
    prepare_test_state()

    response = client.post("/api/tbio/GetMotd", json={"Language": "not_supported"})
    assert response.status_code == 200


def test_client_matchmake_2(client: FlaskClient):
    prepare_test_state()

    ip_address = "42.0.69.42"
    
    registration_response = client.post(
        "/api/v1/servers",
        json={
            "name": "Test Server",
            "description": "Test Description",
            "ports": test_ports,
            "player_count": 0,
            "max_players": 100,
            "current_map": "Test Map",
            "local_ip_address": "192.168.1.2"
        }, headers={"X-Forwarded-For": ip_address}
    )

    unique_id = registration_response.get_json()["server"]["unique_id"]

    response = client.post("/api/playfab/Client/Matchmake", json={"LobbyId": unique_id})
    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json["data"]["ServerHostname"] == ip_address
    assert response_json["data"]["ServerPort"] == 1234

def test_local_client_matchmake(client: FlaskClient):
    prepare_test_state()

    ip_address = "42.0.69.42"
    local_ip_address = "192.168.1.4"
    
    registration_response = client.post(
        "/api/v1/servers",
        json={
            "name": "Test Server",
            "description": "Test Description",
            "ports": test_ports,
            "player_count": 0,
            "max_players": 100,
            "current_map": "Test Map",
            "local_ip_address": local_ip_address

        }, headers={"X-Forwarded-For": ip_address}
    )

    unique_id = registration_response.get_json()["server"]["unique_id"]

    response = client.post("/api/playfab/Client/Matchmake", json={"LobbyId": unique_id}, headers={"X-Forwarded-For": ip_address})
    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json["data"]["ServerHostname"] == local_ip_address
    assert response_json["data"]["ServerPort"] == 1234

def test_motd_no_json(client: FlaskClient):
    prepare_test_state()
    response = client.post("/api/tbio/GetMotd", content_type="application/json")
    assert response.status_code == 400
    assert response.get_json()["status"] == "missing_json_body"

def test_matchmake_no_json(client: FlaskClient):
    prepare_test_state()
    response = client.post("/api/playfab/Client/Matchmake", content_type="application/json")
    assert response.status_code == 400
    assert response.get_json()["status"] == "missing_json_body"
