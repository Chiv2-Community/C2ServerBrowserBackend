from dataclasses import asdict

import pytest

from server_browser_backend.models.base_models import (
    Chivalry2Ports,
    Server,
    ServerListResponse,
    ServerResponse,
    ServerResponseWithIP,
)


@pytest.mark.parametrize("local_ip", [None, "192.168.1.24"])
@pytest.mark.parametrize("include_ip", [False, True])
def test_from_servers_selects_response_model(include_ip, local_ip):
    server = Server(
        unique_id="test-server",
        ip_address="42.0.69.0",
        local_ip_address=local_ip,
        ports=Chivalry2Ports(game=1234, a2s=1235, ping=1236),
        password_protected=False,
        last_heartbeat=1.0,
        name="Test Server",
        description="Test Description",
        current_map="Test Map",
        player_count=0,
        max_players=64,
        is_verified=False,
        mods=[],
    )

    listing = ServerListResponse.from_servers([server], include_ip=include_ip)
    assert len(listing.servers) == 1
    response = listing.servers[0]
    data = asdict(response)

    assert data["unique_id"] == server.unique_id
    assert data["ports"]["game"] == server.ports.game
    if include_ip:
        assert type(response) is ServerResponseWithIP
        assert data["ip_address"] == server.ip_address
        assert data["local_ip_address"] == local_ip
    else:
        assert type(response) is ServerResponse
        assert "ip_address" not in data
        assert "local_ip_address" not in data


@pytest.mark.parametrize("include_ip", [False, True])
def test_from_servers_empty(include_ip):
    assert ServerListResponse.from_servers([], include_ip=include_ip).servers == []
