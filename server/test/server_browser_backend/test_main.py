import pytest
from flask.testing import FlaskClient
from datetime import datetime
from server_browser_backend.main import app, servers, heartbeat_timeout, limiter, KEY_HEADER
from server_browser_backend.models import Heartbeat, SecuredResource

LOCALHOST = "127.0.0.1"

limiter.enabled = False

test_server_json = {
        "name": "Test Server",
        "description": "Test Description",
        "port": 1234,
        "player_count": 0,
        "max_players": 100,
        "current_map": "Test Map"
    }

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_register(client: FlaskClient):
    servers.clear() 

    response = client.post('/servers', json=test_server_json)
    response_json = response.get_json()

    assert response.status_code == 201
    assert 'key' in response_json
    assert 'server' in response_json
    assert 'unique_id' in response_json['server']
    assert response_json['server']['unique_id'] in servers

def test_update(client: FlaskClient):
    servers.clear() 

    registration_response = client.post('/servers', json=test_server_json)
    server_id = registration_response.get_json()['server']['unique_id']
    response = client.put(f'/servers/{server_id}', headers={
        KEY_HEADER: registration_response.get_json()['key'],
    }, json={
        "port": 1234,
        "player_count": 10,
        "max_players": 100,
        "current_map": "Test Map"
    })

    response_json = response.get_json()
    unique_id = response_json['server']['unique_id']

    assert response.status_code == 200
    assert servers[unique_id].get().player_count == 10

def test_heartbeat(client: FlaskClient):
    servers.clear() 

    registration_response = client.post('/servers', json=test_server_json)
    server_id = registration_response.get_json()['server']['unique_id']
    response = client.post(f'/servers/{server_id}/heartbeat', headers={
        KEY_HEADER: registration_response.get_json()['key'],
    }, json={
        "key": registration_response.get_json()['key'],
        "port": 1234,
    })

    assert response.status_code == 200
    assert response.get_json()['refresh_before'] > datetime.now().timestamp()

def test_get_servers(client: FlaskClient):
    servers.clear() 

    response = client.get('/servers')
    assert response.status_code == 200
    assert len(response.get_json()['servers']) == 0

    registration = client.post('/servers', json={
        "name": "Test Server",
        "description": "Test Description",
        "port": 1234,
        "player_count": 0,
        "max_players": 100,
        "current_map": "Test Map"
    })

    response = client.get('/servers')
    assert response.status_code == 200
    assert len(response.get_json()['servers']) == 1

def test_heartbeat_timeout(client: FlaskClient):
    servers.clear() 

    registration_response = client.post('/servers', json={
        "name": "Test Server",
        "description": "Test Description",
        "port": 1234,
        "player_count": 0,
        "max_players": 100,
        "current_map": "Test Map"
    })

    response_json = registration_response.get_json()
    unique_id = response_json["server"]["unique_id"]

    # Force expiration. 
    result = servers[unique_id].update(
        response_json["key"],
        lambda server: server.with_heartbeat(
            Heartbeat(
                server.unique_id,
                server.ip_address,
                server.port
            ),
            datetime.now().timestamp() - heartbeat_timeout - 1
        )
    )

    assert result is not None

    servers[unique_id] = result

    response = client.get('/servers')
    assert response.status_code == 200
    assert len(response.get_json()['servers']) == 0

def test_bad_json_missing_key(client: FlaskClient):
    servers.clear() 

    response = client.post('/servers', json={
        "name": "Test Server",
        "description": "Test Description",
        "port": 1234,
        "player_count": 0,
        "max_players": 100
    })

    assert response.status_code == 400
    assert "current_map" in response.get_json()["error"], "Error response did not contain the missing key"

def test_bad_json_invalid_type(client: FlaskClient):
    servers.clear() 

    response = client.post('/servers', json={
        "name": "Test Server",
        "description": "Test Description",
        "port": 1234,
        "player_count": "0",
        "max_players": 100,
        "current_map": "Test Map"
    })
    
    response_json = response.get_json()
    assert response.status_code == 400
    assert "player_count" in response_json["error"], "Error response did not contain the key of the invalid type"
    assert "int" in response_json["error"], "Error response did not contain the correct type of the invalid key"
    assert "str" in response_json["error"], "Error response did not contain the actual type of the invalid key"
