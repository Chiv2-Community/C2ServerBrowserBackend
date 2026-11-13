from datetime import datetime

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from server_browser_backend.routes import shared
from ipaddress import ip_network

from . import prepare_test_state

test_ports = {"game": 1234, "ping": 1235, "a2s": 1236}

test_mods = [
    {
        "organization": "Active mod",
        "name": "Test Mod",
        "version": "1.0.0",
        "active": True,
    },
    {
        "organization": "Inactive mod",
        "name": "Test Mod 2",
        "version": "1.0.0",
        "active": False,
    }
]

test_server_json = {
    "name": "Test Server",
    "description": "Test Description",
    "ports": test_ports,
    "player_count": 0,
    "max_players": 100,
    "current_map": "Test Map",
    "mods": test_mods
}


def test_register(client: TestClient):
    response = client.post("/api/v1/servers", json=test_server_json)
    response_json = response.json()
    refresh_before = response_json["refresh_before"]

    assert response.status_code == 201
    assert "key" in response_json
    assert "server" in response_json
    assert "unique_id" in response_json["server"]
    assert shared.server_list.exists(response_json["server"]["unique_id"])
    assert [x.is_verified for x in shared.server_list.get_all()][0] == True
    assert refresh_before > datetime.now().timestamp()
    assert len(response_json["server"]["mods"]) == 2
    assert response_json["server"]["mods"][0]["active"] == True
    assert response_json["server"]["mods"][1]["active"] == False

def test_register_unauthorized(client: TestClient):
    prepare_test_state(verified_list=[])

    response = client.post("/api/v1/servers", json=test_server_json)

    assert response.status_code == 201
    assert [x.is_verified for x in shared.server_list.get_all()][0] == False


def test_register_invalid_local_ip(client: TestClient):
    response = client.post(
        "/api/v1/servers", json={**test_server_json, "local_ip_address": "invalid"}
    )
    assert response.status_code == 400
    assert response.json()["status"] == "invalid_json_body"
    assert "local_ip_address" in response.json()["message"]
    assert shared.server_list.get_all() == []

def test_update(client: TestClient):
    registration_response = client.post("/api/v1/servers", json=test_server_json)
    server_id = registration_response.json()["server"]["unique_id"]
    response = client.put(
        f"/api/v1/servers/{server_id}",
        headers={
            shared.KEY_HEADER: registration_response.json()["key"],
        },
        json={"player_count": 10, "max_players": 100, "current_map": "Test Map", "mods": [{"organization": "Active mod", "name": "Updated Mod", "version": "1.0.0", "active": True}]}
    )

    response_json = response.json()
    unique_id = response_json["server"]["unique_id"]
    server = shared.server_list.get(unique_id)


    assert response.status_code == 200

    assert server is not None
    assert server.player_count == 10
    assert server.max_players == 100
    assert len(server.mods) == 1
    assert server.mods[0].name == "Updated Mod"

@pytest.mark.parametrize("heartbeat", [False, True])
@pytest.mark.parametrize(
    "registered_ip, requester_ip, allowed",
    [
        ("127.0.0.1", "127.0.0.1", True),
        ("127.0.0.1", "127.0.0.2", False),
        ("2001:db8::1", "2001:0db8:0:0:0:0:0:1", True),
        ("2001:db8::1", "2001:db8::2", False),
        ("127.0.0.1", "2001:db8::1", False),
    ],
)
def test_update_requester_ip(client_for_ip, heartbeat, registered_ip, requester_ip, allowed):
    registered_client = client_for_ip(registered_ip)
    registration_response = registered_client.post(
        "/api/v1/servers",
        json=test_server_json,
    ).json()
    server_id = registration_response["server"]["unique_id"]
    path = f"/api/v1/servers/{server_id}"
    if heartbeat:
        path += "/heartbeat"

    response = client_for_ip(requester_ip).request(
        "POST" if heartbeat else "PUT", path,
        headers={shared.KEY_HEADER: registration_response["key"]},
        json={"player_count": 10, "max_players": 100, "current_map": "Updated Map"},
    )

    if allowed:
        assert response.status_code == 200
    else:
        assert response.status_code == 401
        assert response.json() == {
            "status": "unauthorized",
            "message": "Invalid IP address",
            "context": None,
        }
        assert shared.server_list.get(server_id) is None
        retry_response = registered_client.request(
            "POST" if heartbeat else "PUT", path,
            headers={shared.KEY_HEADER: registration_response["key"]},
            json={"player_count": 10, "max_players": 100, "current_map": "Test Map"},
        )
        assert retry_response.status_code == 404


@pytest.mark.parametrize("heartbeat", [False, True])
def test_changed_ip_invalid_key_preserves_registration(client: TestClient, client_for_ip, heartbeat):
    registration = client.post("/api/v1/servers", json=test_server_json).json()
    server_id = registration["server"]["unique_id"]
    original_server = shared.server_list.get(server_id)
    path = f"/api/v1/servers/{server_id}"
    if heartbeat:
        path += "/heartbeat"

    response = client_for_ip("127.0.0.2").request(
        "POST" if heartbeat else "PUT", path,
        headers={shared.KEY_HEADER: registration["key"] + "invalid"},
        json={"player_count": 10, "max_players": 100, "current_map": "Updated Map"},
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Invalid secret key"
    assert shared.server_list.get(server_id) == original_server


def test_update_no_mods(client: TestClient):
    registration_response = client.post("/api/v1/servers", json=test_server_json)
    server_id = registration_response.json()["server"]["unique_id"]
    response = client.put(
        f"/api/v1/servers/{server_id}",
        headers={
            shared.KEY_HEADER: registration_response.json()["key"],
        },
        json={"player_count": 10, "max_players": 100, "current_map": "Test Map"}
    )

    response_json = response.json()
    unique_id = response_json["server"]["unique_id"]
    server = shared.server_list.get(unique_id)


    assert response.status_code == 200

    assert server is not None
    assert server.player_count == 10
    assert server.max_players == 100

    # Mods should be unchanged
    assert len(server.mods) == 2


def test_update_non_existent(client: TestClient):
    server_id = 'foo'
    response = client.put(
        f"/api/v1/servers/{server_id}",
        headers={
            shared.KEY_HEADER: 'bar',
        },
        json={"player_count": 10, "max_players": 100, "current_map": "Test Map"},
    )

    assert response.status_code == 404


def test_delete(client: TestClient):
    
    createResponse = client.post("/api/v1/servers", json=test_server_json).json()
    id, key = createResponse["server"]["unique_id"], createResponse["key"]

    deleteResponse = client.delete(
        "/api/v1/servers/{}".format(id), headers={shared.KEY_HEADER: key}
    )

    response_json = deleteResponse.json()
    assert deleteResponse.status_code == 200
    assert response_json["status"] == "deleted"
    assert not shared.server_list.exists(id)


def test_delete_nonexistant_server(client: TestClient):
    deleteResponse = client.delete(
        "/api/v1/servers/not-registered", headers={shared.KEY_HEADER: "Invalid-unused"}
    )

    assert deleteResponse.status_code == 404

def test_register_no_json(client: TestClient):
    response = client.post("/api/v1/servers", headers={"Content-Type": "application/json"})
    assert response.status_code == 400
    assert response.json()["status"] == "missing_json_body"

def test_update_no_json(client: TestClient):
    registration_response = client.post("/api/v1/servers", json=test_server_json)
    server_id = registration_response.json()["server"]["unique_id"]
    response = client.put(
        f"/api/v1/servers/{server_id}",
        headers={
            shared.KEY_HEADER: registration_response.json()["key"],
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 400
    assert response.json()["status"] == "missing_json_body"


def test_delete_no_key(client: TestClient):
    createResponse = client.post("/api/v1/servers", json=test_server_json).json()
    id, key = createResponse["server"]["unique_id"], createResponse["key"]

    deleteResponse = client.delete("/api/v1/servers/{}".format(id))

    assert deleteResponse.status_code == 400


def test_delete_invalid_key(client: TestClient):
    createResponse = client.post("/api/v1/servers", json=test_server_json).json()
    id, key = createResponse["server"]["unique_id"], createResponse["key"]

    deleteResponse = client.delete(
        "/api/v1/servers/{}".format(id), headers={shared.KEY_HEADER: key + "Invalid"}
    )

    assert deleteResponse.status_code == 403


def test_update_no_key(client: TestClient):
    registration_response = client.post("/api/v1/servers", json=test_server_json)
    server_id = registration_response.json()["server"]["unique_id"]
    response = client.put(f"/api/v1/servers/{server_id}", json={})
    assert response.status_code == 400


def test_update_invalid_key(client: TestClient):
    registration_response = client.post("/api/v1/servers", json=test_server_json)
    server_id = registration_response.json()["server"]["unique_id"]
    response = client.put(
        f"/api/v1/servers/{server_id}",
        headers={
            shared.KEY_HEADER: registration_response.json()["key"] + "invalid",
        },
        json={"player_count": 10, "max_players": 100, "current_map": "Test Map"},
    )

    assert response.status_code == 403


def test_heartbeat(client: TestClient):
    registration_response = client.post("/api/v1/servers", json=test_server_json)
    server_id = registration_response.json()["server"]["unique_id"]
    response = client.post(
        f"/api/v1/servers/{server_id}/heartbeat",
        headers={
            shared.KEY_HEADER: registration_response.json()["key"],
        },
        json={"port": 1234},
    )

    assert response.status_code == 200
    assert response.json()["refresh_before"] > datetime.now().timestamp()


def test_heartbeat_no_key(client: TestClient):
    registration_response = client.post("/api/v1/servers", json=test_server_json)
    server_id = registration_response.json()["server"]["unique_id"]
    response = client.post(f"/api/v1/servers/{server_id}/heartbeat")
    assert response.status_code == 400


def test_heartbeat_invalid_key(client: TestClient):
    registration_response = client.post("/api/v1/servers", json=test_server_json)
    server_id = registration_response.json()["server"]["unique_id"]
    response = client.post(
        f"/api/v1/servers/{server_id}/heartbeat",
        headers={shared.KEY_HEADER: "invalid", "Content-Type": "application/json"},
    )

    assert response.status_code == 403


def test_get_servers(client: TestClient):
    response = client.get("/api/v1/servers")
    assert response.status_code == 200
    assert len(response.json()["servers"]) == 0

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
    )

    client.post(
        "/api/v1/servers",
        json={
            "name": "Test Server",
            "description": "Test Description",
            "ports": test_ports,
            "player_count": 0,
            "max_players": 100,
            "password_protected": True,
            "current_map": "Test Map",
        },
    )

    response = client.get("/api/v1/servers")
    assert response.status_code == 200
    assert len(response.json()["servers"]) == 2

    # Make sure 1 is password protected and 1 isnt
    assert response.json()["servers"][0]["password_protected"] != response.json()["servers"][1]["password_protected"]


def test_heartbeat_timeout(client: TestClient):
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

    response_json = registration_response.json()
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
    assert len(response.json()["servers"]) == 0


def test_bad_json_missing_key(client: TestClient):
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
        "current_map" in response.json()["message"]
    ), "Error response did not contain the missing key"


def test_bad_json_invalid_type(client: TestClient):
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

    response_json = response.json()
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


@pytest.mark.parametrize("list_name,field,attribute", [
    ("ban-list", "banned_ips", "ban_list"),
    ("verified-list", "verified_ips", "verified_list"),
])
@pytest.mark.parametrize("remove", [False, True])
@pytest.mark.parametrize("valid_key", [False, True])
def test_change_ip_list(client: TestClient, list_name, field, attribute, remove, valid_key):
    target = "12.34.56.78"
    if remove:
        prepare_test_state(**{attribute: [target]})
    ip_list = getattr(shared, attribute)
    before = ip_list.get_all(shared.ADMIN_KEY).copy()

    response = client.request(
        "DELETE" if remove else "PUT", f"/api/v1/admin/{list_name}",
        json={field: [target]},
        headers={shared.ADMIN_KEY_HEADER: shared.ADMIN_KEY if valid_key else "beep"},
    )

    assert response.status_code == (200 if valid_key else 403)
    expected = before
    if valid_key:
        network = ip_network(target)
        expected = before - {network} if remove else before | {network}
        assert {ip_network(ip) for ip in response.json()[field]} == expected
    assert ip_list.get_all(shared.ADMIN_KEY) == expected

def test_is_banned_true(client: TestClient):
    ban_target = "12.34.56.78"
    prepare_test_state(ban_list=[ban_target])

    response = client.get(f"/api/v1/check-banned/{ban_target}")

    assert response.status_code == 200
    assert response.json()["banned"] == True


def test_is_banned_false(client: TestClient):
    ban_target = "12.34.56.78"
    
    prepare_test_state(ban_list=[ban_target])

    response = client.get(
        f"/api/v1/check-banned/127.0.0.1"
    )

    assert response.status_code == 200
    assert response.json()["banned"] == False

def test_jwks(client: TestClient):
    response = client.get("/api/v1/auth/jwks.json")
    assert response.status_code == 200
    data = response.json()
    assert "keys" in data
    assert len(data["keys"]) == 1
    assert data["keys"][0]["kid"] == "server-browser-backend-key-1"

@patch("server_browser_backend.token_reissuer.TokenReissuer.validate_and_reissue")
def test_login_success(mock_reissue: MagicMock, client: TestClient):
    mock_reissue.return_value = "fake-reissued-token"
    
    response = client.post("/api/v1/auth/login", json={"token": "fake-eos-token"})
    
    assert response.status_code == 200
    assert response.json()["token"] == "fake-reissued-token"
    mock_reissue.assert_called_once_with("fake-eos-token", "127.0.0.1")
