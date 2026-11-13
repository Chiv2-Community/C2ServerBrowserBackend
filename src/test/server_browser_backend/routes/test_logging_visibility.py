"""Lifecycle and rejection logs identify events without exposing credentials."""

import logging

import pytest

from server_browser_backend.routes.shared import ADMIN_KEY_HEADER, KEY_HEADER

REGISTRATION = {
    "name": "Logging test server",
    "description": "",
    "current_map": "Test Map",
    "player_count": 0,
    "max_players": 32,
    "ports": {"game": 7777, "ping": 7778, "a2s": 7779},
}
UPDATE = {"player_count": 2, "max_players": 32, "current_map": "Updated Map"}


def backend_records(caplog):
    return [
        record
        for record in caplog.records
        if record.name.startswith("server_browser_backend.")
    ]


def test_registration_and_deletion_logs_include_server_identity(client, caplog):
    caplog.set_level(logging.INFO)
    registration = client.post("/api/v1/servers", json=REGISTRATION).json()
    server_id, key = registration["server"]["unique_id"], registration["key"]
    deletion = client.delete(f"/api/v1/servers/{server_id}", headers={KEY_HEADER: key})
    assert deletion.status_code == 200
    records = backend_records(caplog)
    assert len(records) == 2
    for record, event in zip(records, ("Server registered", "Server deleted")):
        assert record.levelno == logging.INFO
        message = record.getMessage()
        assert event in message
        assert server_id in message
        assert "name='Logging test server'" in message
        assert "ip=127.0.0.1 game_port=7777" in message
        assert key not in message


@pytest.mark.parametrize("operation", ["update", "heartbeat"])
@pytest.mark.parametrize("credential", ["valid", "invalid", "missing"])
@pytest.mark.parametrize("changed_host", [False, True])
def test_update_logs_identify_rejections_and_host_changes(
    client_for_ip,
    browser,
    caplog,
    operation,
    credential,
    changed_host,
):
    registered = client_for_ip("2001:db8::1")
    registration = registered.post("/api/v1/servers", json=REGISTRATION).json()
    server_id, key = registration["server"]["unique_id"], registration["key"]
    original = browser.server_list.get(server_id)
    requester_ip = "2001:db8::2" if changed_host else "2001:db8::1"
    requester = client_for_ip(requester_ip)
    headers = (
        {}
        if credential == "missing"
        else {KEY_HEADER: key if credential == "valid" else "DO-NOT-LOG-THIS-KEY"}
    )
    suffix = "/heartbeat" if operation == "heartbeat" else ""
    caplog.clear()
    caplog.set_level(logging.INFO)
    response = requester.request(
        "POST" if operation == "heartbeat" else "PUT",
        f"/api/v1/servers/{server_id}{suffix}",
        headers=headers,
        json=UPDATE,
    )
    records = backend_records(caplog)
    messages = "\n".join(record.getMessage() for record in records)
    assert server_id in messages
    assert (
        f"operation={operation}" in messages
        or f"Server {operation} accepted" in messages
    )
    assert f"requester_ip='{requester_ip}'" in messages
    assert key not in messages and "DO-NOT-LOG-THIS-KEY" not in messages
    if credential != "valid":
        assert response.status_code == (400 if credential == "missing" else 403)
        assert f"{credential} secret key" in messages
        assert "registration invalidated" not in messages
        assert browser.server_list.get(server_id) == original
        assert all(record.levelno == logging.WARNING for record in records)
    elif changed_host:
        assert response.status_code == 401
        assert "Server host change detected" in messages
        assert "registered_ip=2001:db8::1" in messages
        assert "Server registration invalidated after host change" in messages
        assert browser.server_list.get(server_id) is None
        assert all(record.levelno == logging.WARNING for record in records)
    else:
        assert response.status_code == 200
        assert f"Server {operation} accepted" in messages
        assert all(record.levelno == logging.INFO for record in records)


@pytest.mark.parametrize("operation", ["update", "heartbeat", "delete"])
def test_unknown_server_logs_warning(client, caplog, operation):
    caplog.set_level(logging.INFO)
    suffix = "/heartbeat" if operation == "heartbeat" else ""
    method = {"update": "PUT", "heartbeat": "POST", "delete": "DELETE"}[operation]
    response = client.request(
        method,
        "/api/v1/servers/unknown" + suffix,
        headers={KEY_HEADER: "not-a-key"},
        json=UPDATE,
    )
    assert response.status_code == 404
    records = backend_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert "not registered" in records[0].getMessage()
    assert "server_id='unknown'" in records[0].getMessage()
    assert "not-a-key" not in caplog.text


def test_invalid_delete_key_logs_warning_and_preserves_registration(
    client, browser, caplog
):
    registration = client.post("/api/v1/servers", json=REGISTRATION).json()
    server_id = registration["server"]["unique_id"]
    caplog.clear()
    caplog.set_level(logging.INFO)
    assert (
        client.delete(
            f"/api/v1/servers/{server_id}", headers={KEY_HEADER: "secret-do-not-log"}
        ).status_code
        == 403
    )
    assert browser.server_list.get(server_id) is not None
    (record,) = backend_records(caplog)
    assert record.levelno == logging.WARNING
    assert "invalid secret key operation=delete_server" in record.getMessage()
    assert server_id in record.getMessage()
    assert "secret-do-not-log" not in caplog.text


@pytest.mark.parametrize("list_name", ["ban-list", "verified-list"])
def test_admin_read_rejections_log_without_credentials(client, caplog, list_name):
    caplog.set_level(logging.INFO)
    assert (
        client.get(
            f"/api/v1/admin/{list_name}",
            headers={ADMIN_KEY_HEADER: "private-admin-key"},
        ).status_code
        == 403
    )
    (record,) = backend_records(caplog)
    assert record.levelno == logging.WARNING
    assert "invalid admin key" in record.getMessage()
    assert "requester_ip='127.0.0.1'" in record.getMessage()
    assert "private-admin-key" not in caplog.text


def test_expiry_logs_server_identity_without_credentials(client, browser, caplog):
    registration = client.post("/api/v1/servers", json=REGISTRATION).json()
    server_id = registration["server"]["unique_id"]
    browser.server_list.update(
        server_id, registration["key"], lambda server: server.with_heartbeat(0)
    )
    caplog.clear()
    caplog.set_level(logging.INFO)
    assert client.get("/api/v1/servers").json()["servers"] == []
    (record,) = backend_records(caplog)
    assert record.levelno == logging.INFO
    assert "Server registration expired" in record.getMessage()
    assert server_id in record.getMessage()
    assert "timeout_seconds=65" in record.getMessage()
    assert registration["key"] not in caplog.text


def test_server_name_cannot_inject_log_lines(client, caplog):
    caplog.set_level(logging.INFO)
    assert (
        client.post(
            "/api/v1/servers", json={**REGISTRATION, "name": "server\nFORGED EVENT\r"}
        ).status_code
        == 201
    )
    (record,) = backend_records(caplog)
    assert "server\\nFORGED EVENT\\r" in record.getMessage()
    assert "\n" not in record.getMessage() and "\r" not in record.getMessage()


def test_unexpected_failure_logs_request_context_and_traceback(
    client, browser, caplog, monkeypatch
):
    def fail_listing():
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(browser.server_list, "get_all", fail_listing)
    caplog.set_level(logging.INFO)
    assert (
        client.get(
            "/api/v1/servers", headers={"X-Forwarded-For": "192.0.2.17"}
        ).status_code
        == 500
    )
    (record,) = backend_records(caplog)
    assert record.levelno == logging.ERROR
    assert "operation=get_servers method=GET" in record.getMessage()
    assert "requester_ip='192.0.2.17'" in record.getMessage()
    assert "registry unavailable" in record.getMessage()
    assert record.exc_info is not None


@pytest.mark.parametrize(
    "body",
    [
        None,
        {},
        {**REGISTRATION, "player_count": "BODY-SECRET"},
        {**REGISTRATION, "player_count": True},
    ],
)
def test_validation_logs_omit_body_headers_and_query_strings(client, caplog, body):
    caplog.set_level(logging.INFO)
    response = client.post(
        "/api/v1/servers?token=QUERY-SECRET",
        json=body,
        headers={"Authorization": "Bearer HEADER-SECRET"},
    )
    assert response.status_code == 400
    (record,) = backend_records(caplog)
    assert record.levelno == logging.WARNING
    message = record.getMessage()
    assert "Request rejected:" in message
    assert "operation=register method=POST" in message
    assert all(
        secret not in message
        for secret in ("BODY-SECRET", "HEADER-SECRET", "QUERY-SECRET")
    )


def test_banned_request_logs_warning(client, browser, admin_key, caplog):
    browser.ban_list.add(admin_key, "127.0.0.1")
    caplog.set_level(logging.INFO)
    assert client.get("/api/v1/servers").status_code == 403
    (record,) = backend_records(caplog)
    assert record.levelno == logging.WARNING
    assert (
        "Request rejected: banned requester operation=get_servers"
        in record.getMessage()
    )
