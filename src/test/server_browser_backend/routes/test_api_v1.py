from datetime import datetime
from os import getenv

import pytest
from flask.testing import FlaskClient

from server_browser_backend.main import app
from server_browser_backend.routes import shared

LOCALHOST = "127.0.0.1"


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


def test_register(client: FlaskClient):
    shared.server_list.clear()

    response = client.post("/api/v1/servers", json=test_server_json)
    response_json = response.get_json()

    assert response.status_code == 201
    assert "key" in response_json
    assert "server" in response_json
    assert "unique_id" in response_json["server"]
    assert shared.server_list.exists(response_json["server"]["unique_id"])


def test_update(client: FlaskClient):
    shared.server_list.clear()

    registration_response = client.post("/api/v1/servers", json=test_server_json)
    server_id = registration_response.get_json()["server"]["unique_id"]
    response = client.put(
        f"/api/v1/servers/{server_id}",
        headers={
            shared.KEY_HEADER: registration_response.get_json()["key"],
        },
        json={"player_count": 10, "max_players": 100, "current_map": "Test Map"},
    )

    response_json = response.get_json()
    unique_id = response_json["server"]["unique_id"]
    server = shared.server_list.get(unique_id)

    assert response.status_code == 200

    assert server is not None
    assert server.player_count == 10


def test_delete(client: FlaskClient):
    shared.server_list.clear()

    createResponse = client.post("/api/v1/servers", json=test_server_json).get_json()
    id, key = createResponse["server"]["unique_id"], createResponse["key"]

    deleteResponse = client.delete(
        "/api/v1/servers/{}".format(id), headers={shared.KEY_HEADER: key}
    )

    response_json = deleteResponse.get_json()
    assert deleteResponse.status_code == 200
    assert response_json["status"] == "deleted"
    assert not shared.server_list.exists(id)


def test_delete_nonexistant_server(client: FlaskClient):
    shared.server_list.clear()

    deleteResponse = client.delete(
        "/api/v1/servers/{}".format(id), headers={shared.KEY_HEADER: "Invalid-unused"}
    )

    assert deleteResponse.status_code == 404


def test_delete_no_key(client: FlaskClient):
    shared.server_list.clear()

    createResponse = client.post("/api/v1/servers", json=test_server_json).get_json()
    id, key = createResponse["server"]["unique_id"], createResponse["key"]

    deleteResponse = client.delete("/api/v1/servers/{}".format(id))

    assert deleteResponse.status_code == 400


def test_delete_invalid_key(client: FlaskClient):
    shared.server_list.clear()

    createResponse = client.post("/api/v1/servers", json=test_server_json).get_json()
    id, key = createResponse["server"]["unique_id"], createResponse["key"]

    deleteResponse = client.delete(
        "/api/v1/servers/{}".format(id), headers={shared.KEY_HEADER: key + "Invalid"}
    )

    assert deleteResponse.status_code == 403


def test_update_no_key(client: FlaskClient):
    shared.server_list.clear()

    registration_response = client.post("/api/v1/servers", json=test_server_json)
    server_id = registration_response.get_json()["server"]["unique_id"]
    response = client.put(f"/api/v1/servers/{server_id}", json={})
    assert response.status_code == 400


def test_update_invalid_key(client: FlaskClient):
    registration_response = client.post("/api/v1/servers", json=test_server_json)
    server_id = registration_response.get_json()["server"]["unique_id"]
    response = client.put(
        f"/api/v1/servers/{server_id}",
        headers={
            shared.KEY_HEADER: registration_response.get_json()["key"] + "invalid",
        },
        json={"player_count": 10, "max_players": 100, "current_map": "Test Map"},
    )

    assert response.status_code == 403


def test_heartbeat(client: FlaskClient):
    shared.server_list.clear()

    registration_response = client.post("/api/v1/servers", json=test_server_json)
    server_id = registration_response.get_json()["server"]["unique_id"]
    response = client.post(
        f"/api/v1/servers/{server_id}/heartbeat",
        headers={
            shared.KEY_HEADER: registration_response.get_json()["key"],
        },
        json={"port": 1234},
    )

    assert response.status_code == 200
    assert response.get_json()["refresh_before"] > datetime.now().timestamp()


def test_heartbeat_no_key(client: FlaskClient):
    shared.server_list.clear()

    registration_response = client.post("/api/v1/servers", json=test_server_json)
    server_id = registration_response.get_json()["server"]["unique_id"]
    response = client.post(f"/api/v1/servers/{server_id}/heartbeat")
    assert response.status_code == 400


def test_heartbeat_invalid_key(client: FlaskClient):
    shared.server_list.clear()

    registration_response = client.post("/api/v1/servers", json=test_server_json)
    server_id = registration_response.get_json()["server"]["unique_id"]
    response = client.post(
        f"/api/v1/servers/{server_id}/heartbeat",
        headers={shared.KEY_HEADER: "invalid", "Content-Type": "application/json"},
    )

    assert response.status_code == 403


def test_get_servers(client: FlaskClient):
    shared.server_list.clear()

    response = client.get("/api/v1/servers")
    assert response.status_code == 200
    assert len(response.get_json()["servers"]) == 0

    registration = client.post(
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

    response = client.get("/api/v1/servers")
    assert response.status_code == 200
    assert len(response.get_json()["servers"]) == 1


def test_heartbeat_timeout(client: FlaskClient):
    shared.server_list.clear()

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

    response_json = registration_response.get_json()
    unique_id = response_json["server"]["unique_id"]

    # Force expiration.
    result = shared.server_list.update(
        unique_id,
        response_json["key"],
        lambda server: server.with_heartbeat(
            datetime.now().timestamp() - shared.heartbeat_timeout - 1
        ),
    )

    assert result is not None

    response = client.get("/api/v1/servers")
    assert response.status_code == 200
    assert len(response.get_json()["servers"]) == 0


def test_bad_json_missing_key(client: FlaskClient):
    shared.server_list.clear()

    response = client.post(
        "/api/v1/servers",
        json={
            "name": "Test Server",
            "description": "Test Description",
            "ports": test_ports,
            "player_count": 0,
            "max_players": 100,
        },
    )

    assert response.status_code == 400
    assert (
        "current_map" in response.get_json()["message"]
    ), "Error response did not contain the missing key"


def test_bad_json_invalid_type(client: FlaskClient):
    shared.server_list.clear()

    response = client.post(
        "/api/v1/servers",
        json={
            "name": "Test Server",
            "description": "Test Description",
            "ports": test_ports,
            "player_count": "0",
            "max_players": 100,
            "current_map": "Test Map",
        },
    )

    response_json = response.get_json()
    assert response.status_code == 400
    assert (
        "player_count" in response_json["message"]
    ), "Error response did not contain the key of the invalid type"
    assert (
        "int" in response_json["message"]
    ), "Error response did not contain the correct type of the invalid key"
    assert (
        "str" in response_json["message"]
    ), "Error response did not contain the actual type of the invalid key"


def test_add_to_ban_list(client: FlaskClient):
    shared.ban_list.clear(shared.ADMIN_KEY)

    ban_targets = ["12.34.56.78"]
    response = client.post(
        "/api/v1/admin/ban-list",
        json={"ban_ips": ban_targets},
        headers={shared.ADMIN_KEY_HEADER: getenv("ADMIN_KEY")},
    )

    assert response.status_code == 200
    assert len(shared.ban_list) == 1


def test_add_to_ban_list_invalid_key(client: FlaskClient):
    shared.ban_list.clear(shared.ADMIN_KEY)

    ban_targets = ["12.34.56.78"]
    response = client.post(
        "/api/v1/admin/ban-list",
        json={"ban_ips": ban_targets},
        headers={shared.ADMIN_KEY_HEADER: "beep"},
    )

    assert response.status_code == 403
    assert len(shared.ban_list) == 0

def test_add_to_allow_list(client: FlaskClient):
    shared.allow_list.clear(shared.ADMIN_KEY)

    allow_targets = ["12.34.56.78"]
    response = client.post(
        "/api/v1/admin/allow-list",
        json={"allowed_ips": allow_targets},
        headers={shared.ADMIN_KEY_HEADER: getenv("ADMIN_KEY")},
    )

    assert response.status_code == 200
    assert len(shared.allow_list) == 1

def test_add_to_allow_list_invalid_key(client: FlaskClient):
    shared.allow_list.clear(shared.ADMIN_KEY)

    allow_targets = ["12.34.56.78"]
    response = client.post(
        "/api/v1/admin/allow-list",
        json={"allowed_ips": allow_targets},
        headers={shared.ADMIN_KEY_HEADER: "beep"},
    )

    assert response.status_code == 403
    assert len(shared.allow_list) == 0
