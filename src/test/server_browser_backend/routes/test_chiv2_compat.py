from datetime import datetime

import pytest
from flask.testing import FlaskClient

from server_browser_backend.main import app
from server_browser_backend.routes import shared
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

    response = client.post("/api/tbio/GetCurrentGames")
    assert response.status_code == 200
    assert len(response.get_json()["Data"]["Games"]) == 1

    client.post(
        "/api/v1/servers",
        json={
            "name": "Test Server",
            "description": "Test Description",
            "ports": test_ports,
            "player_count": 0,
            "max_players": 100,
            "current_map": "Test Map",
        },
        headers={"X-Forwarded-For": source_ip}
    )

    response = client.post("/api/tbio/GetCurrentGames")
    assert response.status_code == 200
    assert len(response.get_json()["Data"]["Games"]) == 2

    ip_addresses = [server["ServerIPV4Address"] for server in response.get_json()["Data"]["Games"]]
    assert source_ip in ip_addresses
    assert "127.0.0.1" in ip_addresses

def test_motd_endpoint(client: FlaskClient):
    prepare_test_state()

    response = client.post("/api/tbio/GetMotd", json={"Language": "test"})
    assert response.status_code == 200
    assert response.get_json()["Data"]["Motd"] == "test"


def test_motd_endpoint_default(client: FlaskClient):
    prepare_test_state()

    response = client.post("/api/tbio/GetMotd", json={})
    assert response.status_code == 200


def test_motd_endpoint_fallback(client: FlaskClient):
    prepare_test_state()

    response = client.post("/api/tbio/GetMotd", json={"Language": "not_supported"})
    assert response.status_code == 200


def test_client_matchmake(client: FlaskClient):
    prepare_test_state()
    
    registration_response = client.post(
        "/api/v1/servers",
        json={
            "name": "Test Server",
            "description": "Test Description",
            "ports": test_ports,
            "player_count": 0,
            "max_players": 100,
            "current_map": "Test Map",
        },
    )

    unique_id = registration_response.get_json()["server"]["unique_id"]

    response = client.post("/api/playfab/Client/Matchmake", json={"LobbyId": unique_id})
    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json["data"]["ServerHostname"] == "127.0.0.1"
    assert response_json["data"]["ServerPort"] == 1234
