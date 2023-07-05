import pytest
from flask.testing import FlaskClient
from datetime import datetime
from server_browser_backend.main import app, servers, heartbeat_timeout, limiter

LOCALHOST = "127.0.0.1"

limiter.enabled = False

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_register(client: FlaskClient):
    servers.clear() 

    response = client.post('/register', json={
        "name": "Test Server",
        "description": "Test Description",
        "port": 1234,
        "player_count": 0,
        "max_players": 100,
        "current_map": "Test Map"
    })
    assert response.status_code == 201
    assert response.get_json()['status'] == 'registered'
    assert (LOCALHOST, 1234) in servers

def test_heartbeat(client: FlaskClient):
    servers.clear() 

    client.post('/register', json={
        "name": "Test Server",
        "description": "Test Description",
        "port": 1234,
        "player_count": 0,
        "max_players": 100,
        "current_map": "Test Map"
    })
    response = client.post('/heartbeat', json={
        "port": 1234,
        "player_count": 10,
        "max_players": 100,
        "current_map": "Test Map"
    })

    assert response.status_code == 200
    assert response.get_json()['status'] == 'heartbeat received'
    assert servers[(LOCALHOST, 1234)].player_count == 10

def test_get_servers(client: FlaskClient):
    servers.clear() 

    response = client.get('/servers')
    assert response.status_code == 200
    assert len(response.get_json()['servers']) == 0

    registration = client.post('/register', json={
        "name": "Test Server",
        "description": "Test Description",
        "port": 1234,
        "player_count": 0,
        "max_players": 100,
        "current_map": "Test Map"
    })

    print(registration.get_json())

    response = client.get('/servers')
    assert response.status_code == 200
    assert len(response.get_json()['servers']) == 1

def test_heartbeat_timeout(client: FlaskClient):
    servers.clear() 

    client.post('/register', json={
        "name": "Test Server",
        "description": "Test Description",
        "port": 1234,
        "player_count": 0,
        "max_players": 100,
        "current_map": "Test Map"
    })

    # Force expiration. Should probably do this in a nicer way
    servers[(LOCALHOST, 1234)].last_heartbeat = datetime.now().timestamp() - heartbeat_timeout - 1

    response = client.get('/servers')
    assert response.status_code == 200
    assert len(response.get_json()['servers']) == 0

def test_bad_json_missing_key(client: FlaskClient):
    servers.clear() 

    response = client.post('/register', json={
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

    response = client.post('/register', json={
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
