import pytest
from flask.testing import FlaskClient
from datetime import datetime
from server_browser_backend import app, servers, heartbeat_timeout  

LOCALHOST = "127.0.0.1"

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_register(client: FlaskClient):
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
    client.post('/register', json={
        "name": "Test Server",
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
    client.post('/register', json={
        "name": "Test Server",
        "port": 1234,
        "player_count": 0,
        "max_players": 100,
        "current_map": "Test Map"
    })
    response = client.get('/servers')
    assert response.status_code == 200
    assert len(response.get_json()['servers']) == 1

def test_heartbeat_timeout(client: FlaskClient):
    client.post('/register', json={
        "name": "Test Server",
        "description": "Test Description",
        "port": 1234,
        "player_count": 0,
        "max_players": 100,
        "current_map": "Test Map"
    })
    servers[(LOCALHOST, 1234)].last_heartbeat = datetime.now().timestamp() - heartbeat_timeout - 1
    response = client.get('/servers')
    assert response.status_code == 200
    assert len(response.get_json()['servers']) == 0

