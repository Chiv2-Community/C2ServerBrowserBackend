"""Typed generated IP fields and their raw/legacy wire representations."""
from ipaddress import IPv4Address, IPv6Address, ip_address

import pytest
from pydantic import TypeAdapter, ValidationError

from server_browser_api.models import PlayfabGame, ServerResponseWithIP, ServerRegistrationRequest, TbioGame
from server_browser_api.runtime import IPAddress, LegacyIPAddress, DictTypeError, to_wire
from server_browser_backend.models.base_models import Server, server_listing
from server_browser_backend.models.tbio import game_from_server


@pytest.mark.parametrize("value,canonical", [
    ("192.0.2.1", "192.0.2.1"),
    ("2001:0db8:0:0:0:0:0:1", "2001:db8::1"),
    ("[2001:0db8:0:0:0:0:0:1]", "2001:db8::1"),
    ("::1", "::1"),
    ("[::]", "::"),
    ("::ffff:192.0.2.1", "::ffff:c000:201"),
])
def test_ip_types_parse_to_objects_and_serialize_by_protocol(value, canonical):
    for annotation in (IPAddress, LegacyIPAddress):
        adapter = TypeAdapter(annotation)
        parsed = adapter.validate_python(value)
        assert isinstance(parsed, (IPv4Address, IPv6Address))
        assert parsed == ip_address(canonical)
        assert adapter.validate_python(parsed) is parsed
        literal = str(ip_address(canonical))
        expected = f"[{literal}]" if annotation is LegacyIPAddress and parsed.version == 6 else literal
        assert adapter.dump_python(parsed, mode="json") == expected
        assert adapter.validate_json(adapter.dump_json(parsed)) == parsed


@pytest.mark.parametrize("value", [
    "", "hostname.example", "192.0.2.999", "2001:db8::gg", "2001:db8::/64",
    "[192.0.2.1]", "[[2001:db8::1]]", "[2001:db8::1", "2001:db8::1]",
    "[2001:db8::1]:7777", "http://[2001:db8::1]", 1234, True, None,
])
def test_ip_types_reject_non_addresses(value):
    for annotation in (IPAddress, LegacyIPAddress):
        with pytest.raises(ValidationError):
            TypeAdapter(annotation).validate_python(value)


@pytest.mark.parametrize("local", ["192.168.1.1", "fd00::1", "[fd00:0:0:0:0:0:0:1]"])
def test_registration_and_response_fields_remain_typed_until_serialization(local):
    registration = ServerRegistrationRequest.from_json({
        "ports": {"game": 7777, "ping": 7778, "a2s": 7779}, "name": "typed IP",
        "description": "", "current_map": "map", "player_count": 0, "max_players": 32,
        "local_ip_address": local,
    })
    assert isinstance(registration.local_ip_address, (IPv4Address, IPv6Address))
    server = Server.create_after_registration(registration, "server-id", "2001:db8::1", 1.0)
    assert server.local_ip_address is registration.local_ip_address
    diagnostic = server_listing([server], include_ip=True)
    response = diagnostic.servers[0]
    assert isinstance(response, ServerResponseWithIP)
    assert response.ip_address is server.ip_address
    assert response.local_ip_address is server.local_ip_address
    wire = to_wire(diagnostic)
    assert wire["servers"][0]["ip_address"] == "2001:db8::1"
    assert wire["servers"][0]["local_ip_address"] == str(server.local_ip_address)
    assert "ip_address" not in to_wire(server_listing([server], include_ip=False))["servers"][0]
    assert ServerResponseWithIP.from_json(wire["servers"][0]) == response

    tbio = game_from_server(server, server.ip_address)
    assert isinstance(tbio.server_hostname, (IPv4Address, IPv6Address))
    assert tbio.server_hostname == server.local_ip_address
    assert server.local_ip_address is not None
    legacy = f"[{server.local_ip_address}]" if server.local_ip_address.version == 6 else str(server.local_ip_address)
    assert to_wire(tbio)["ServerHostname"] == legacy
    assert to_wire(tbio)["ServerIPV4Address"] == legacy
    assert TbioGame.from_json(to_wire(tbio)) == tbio
    playfab = PlayfabGame(server_hostname=server.ip_address, server_ipv4_address=server.ip_address, server_port=7777, ticket="ticket")
    assert isinstance(playfab.server_hostname, IPv6Address)
    assert to_wire(playfab)["ServerHostname"] == "2001:db8::1"
    assert to_wire(playfab)["ServerIPV4Address"] == "2001:db8::1"


def test_generated_constructor_and_json_decoder_both_validate_addresses():
    fields = {"ServerHostname": "not-an-ip", "ServerIPV4Address": "192.0.2.1", "ServerPort": 7777, "Ticket": "ticket"}
    with pytest.raises(ValidationError):
        PlayfabGame.model_validate(fields)
    with pytest.raises(DictTypeError):
        PlayfabGame.from_json(fields)
