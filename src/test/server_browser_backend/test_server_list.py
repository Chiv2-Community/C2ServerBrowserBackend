"""Registry credential and heartbeat-expiry semantics."""

from datetime import datetime

import pytest
from server_browser_models.models import Chivalry2Ports, ServerRegistrationRequest

import server_browser_backend.server_list as registry
from server_browser_backend.models.base_models import Server
from server_browser_backend.server_list import InvalidSecretKey, ServerList


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
