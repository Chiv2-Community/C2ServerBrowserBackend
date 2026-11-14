"""Registry credential and heartbeat-expiry semantics."""

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from ipaddress import ip_address

import pytest
from server_browser_models.models import Chivalry2Ports, ServerRegistrationRequest

import server_browser_backend.server_list as registry
from server_browser_backend.models.base_models import Server
from server_browser_backend.server_list import InvalidSecretKey, RegistryCapacity, ServerList


@pytest.fixture
def server():
    registration = ServerRegistrationRequest(
        name="test",
        description="",
        current_map="test",
        player_count=0,
        max_players=32,
        ports=Chivalry2Ports(game=7777, ping=7778, a2s=7779),
    )
    return Server.create_after_registration(
        registration, "server-id", "192.0.2.1", 100.0
    )


def test_delete_checks_credentials_and_returns_removed_server(server):
    servers = ServerList()
    key = servers.register(server)
    with pytest.raises(InvalidSecretKey):
        servers.delete(server.unique_id, key + "invalid")
    assert servers.get(server.unique_id) is server
    assert servers.delete(server.unique_id, key) is server
    assert servers.get(server.unique_id) is None
    assert servers.delete(server.unique_id, key) is None


@pytest.mark.parametrize(
    "heartbeat, expired", [(34.0, True), (35.0, False), (36.0, False)]
)
def test_only_listing_processes_expiry_with_a_strict_timeout(
    server, monkeypatch, heartbeat, expired
):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(100.0, tz)

    monkeypatch.setattr(registry, "datetime", Clock)
    servers = ServerList(heartbeat_timeout=65)
    server = server.with_heartbeat(heartbeat)
    servers.register(server)

    assert servers.get(server.unique_id) is server
    assert servers.get_all() == ([] if expired else [server])
    assert servers.get(server.unique_id) == (None if expired else server)


def test_expiry_logging_does_not_hold_the_registry_lock(server, monkeypatch):
    servers = ServerList()
    servers.register(server.with_heartbeat(0))
    events = []

    def log_event(message, *arguments):
        assert not servers.servers_mutex.locked()
        assert servers.get(server.unique_id) is None
        events.append(message % arguments)

    monkeypatch.setattr(registry.logger, "info", log_event)
    assert servers.get_all() == []
    assert len(events) == 1
    assert "Server registration expired" in events[0]


def test_registration_enforces_global_and_ip_budgets_without_eviction(server):
    servers = ServerList(max_servers=2, max_servers_per_ip=1)
    first = server.with_heartbeat(datetime.now().timestamp())
    first_key = servers.register(first)
    with pytest.raises(RegistryCapacity):
        servers.register(replace(first, unique_id="same-ip"))
    other = replace(first, unique_id="other", ip_address=ip_address("192.0.2.2"))
    servers.register(other)
    with pytest.raises(RegistryCapacity):
        servers.register(replace(first, unique_id="third", ip_address=ip_address("192.0.2.3")))
    assert servers.get_all() == [first, other]
    assert servers.delete(first.unique_id, first_key) is first
    servers.register(replace(first, unique_id="third"))
    assert len(servers.get_all()) == 2


def test_registration_reclaims_expired_capacity_without_listing(server, monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(now[0], tz)

    now = [100.0]
    monkeypatch.setattr(registry, "datetime", Clock)
    servers = ServerList(max_servers=1, max_servers_per_ip=1)
    servers.register(server)
    now[0] = 166.0
    fresh = replace(server, unique_id="fresh", last_heartbeat=166.0)
    servers.register(fresh)
    assert servers.get(server.unique_id) is None
    assert servers.get(fresh.unique_id) is fresh


@pytest.mark.parametrize("per_ip", [False, True])
def test_concurrent_registrations_cannot_overrun_budgets(server, per_ip):
    servers = ServerList(max_servers=4, max_servers_per_ip=2 if per_ip else 4)
    server = server.with_heartbeat(datetime.now().timestamp())

    def register(index):
        candidate = replace(server, unique_id=str(index), ip_address=server.ip_address if per_ip else ip_address(f"192.0.2.{index + 1}"))
        try:
            servers.register(candidate)
        except RegistryCapacity:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as executor:
        accepted = list(executor.map(register, range(16)))
    assert sum(accepted) == (2 if per_ip else 4)
    assert len(servers.get_all()) == sum(accepted)


@pytest.mark.parametrize("option,value", [("max_servers", 0), ("max_servers_per_ip", -1), ("max_servers", True)])
def test_invalid_registration_budgets_fail_closed(option, value):
    with pytest.raises(ValueError, match="positive integers"):
        ServerList(**{option: value})
