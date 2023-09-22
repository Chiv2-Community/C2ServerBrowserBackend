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