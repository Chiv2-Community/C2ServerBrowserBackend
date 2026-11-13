from dataclasses import asdict
from server_browser_api.runtime import to_wire
from ipaddress import IPv4Address, IPv6Address, ip_address

import pytest

from server_browser_api.models import ServerRegistrationRequest, UpdateRegisteredServer
from server_browser_backend.models.base_models import Server


@pytest.mark.parametrize(
    "public_ip, local_ip, address_type",
    [
        ("192.0.2.1", "192.168.1.1", IPv4Address),
        ("2001:0db8:0:0:0:0:0:1", "fd00::1", IPv6Address),
        ("192.0.2.1", None, IPv4Address),
    ],
)
def test_server_stores_parsed_addresses(public_ip, local_ip, address_type):
    registration = ServerRegistrationRequest.from_json({
        "ports": {"game": 1234, "a2s": 1235, "ping": 1236},
        "name": "Test Server",
        "description": "",
        "current_map": "Test Map",
        "player_count": 0,
        "max_players": 100,
        **({"local_ip_address": local_ip} if local_ip is not None else {}),
    })
    server = Server.create_after_registration(registration, "server-id", public_ip, 1.0)
    assert isinstance(server.ip_address, address_type)
    assert server.ip_address == ip_address(public_ip)
    assert server.local_ip_address == (ip_address(local_ip) if local_ip else None)
    assert server.address_for(server.ip_address) is (
        server.local_ip_address if server.local_ip_address is not None else server.ip_address
    )
    assert server.address_for(ip_address("198.51.100.2")) is server.ip_address
    assert server.address_for(None) is server.ip_address

    serialized = to_wire(asdict(server))
    serialized["ip_address"] = str(server.ip_address)
    if local_ip is None:
        del serialized["local_ip_address"]
    else:
        serialized["local_ip_address"] = str(server.local_ip_address)
    assert Server.from_json(serialized) == server

    for updated in (
        server.with_heartbeat(2.0),
        server.with_update(UpdateRegisteredServer(current_map="New Map", player_count=1, max_players=100, mods=None)),
        server.verified(),
        server.unverified(),
    ):
        assert updated.ip_address is server.ip_address
        assert updated.local_ip_address is server.local_ip_address
