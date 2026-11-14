"""Regression tests for credentials, proxy trust, and bounded JSON ingestion."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from server_browser_fastapi.runtime import PayloadTooLarge, read_body
from server_browser_models.runtime import contract
from starlette.requests import Request

from server_browser_backend.secured_resource import SecuredResource


@pytest.mark.parametrize("key", ["", "non-ascii-\u00e9"])
def test_insecure_configured_keys_fail_closed(key):
    with pytest.raises(ValueError, match="nonempty ASCII"):
        SecuredResource(key, None)


def test_non_ascii_request_key_is_rejected_without_an_exception():
    assert not SecuredResource("secret", None).validate("\u00e9")


def test_untrusted_peer_cannot_bypass_bans_with_forwarded_headers(
    app, browser, admin_key
):
    browser.ban_list.add(admin_key, "192.0.2.20")
    with TestClient(app, client=("192.0.2.20", 1234)) as client:
        response = client.get(
            "/api/v1/servers", headers={"X-Forwarded-For": "127.0.0.1"}
        )
    assert response.status_code == 403


@pytest.mark.parametrize("trusted,expected", [((), 403), (("192.0.2.0/24",), 200)])
def test_proxy_trust_is_explicitly_configurable(
    app_factory, admin_key, trusted, expected
):
    app = app_factory(trusted_proxies=trusted)
    app.browser_api.ban_list.add(admin_key, "192.0.2.20")
    with TestClient(app, client=("192.0.2.20", 1234)) as client:
        response = client.get(
            "/api/v1/servers", headers={"X-Forwarded-For": "198.51.100.1"}
        )
    assert response.status_code == expected


def test_untrusted_peer_cannot_impersonate_verified_host(app, browser):
    @app.get("/security-probe")
    def probe(request: Request):
        assert request.client is not None
        return {"ip": request.client.host, "scheme": request.url.scheme}

    with TestClient(app, client=("192.0.2.20", 1234)) as client:
        response = client.get(
            "/security-probe",
            headers={
                "X-Forwarded-For": "127.0.0.1",
                "X-Forwarded-Proto": "https",
            },
        )
    assert response.json() == {"ip": "192.0.2.20", "scheme": "http"}


@pytest.mark.parametrize("peer", ["127.0.0.1", "::1"])
def test_trusted_proxy_only_accepts_valid_forwarded_values(app, peer):
    @app.get("/security-probe")
    def probe(request: Request):
        assert request.client is not None
        return {"ip": request.client.host, "scheme": request.url.scheme}

    with TestClient(app, client=(peer, 1234)) as client:
        response = client.get(
            "/security-probe",
            headers={
                "X-Forwarded-For": "192.0.2.1, 2001:db8::2",
                "X-Forwarded-Proto": "https",
            },
        )
        assert response.json() == {"ip": "2001:db8::2", "scheme": "https"}
        response = client.get(
            "/security-probe",
            headers={
                "X-Forwarded-For": "not-an-ip",
                "X-Forwarded-Proto": "javascript",
            },
        )
    assert response.json() == {"ip": peer, "scheme": "http"}


def test_oversized_json_returns_413_without_echoing_content(app):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login", json={"token": "secret-sentinel" * 100000}
        )
    assert response.status_code == 413
    assert response.json()["status"] == "payload_too_large"
    assert "secret-sentinel" not in response.text


@pytest.mark.parametrize("declared", [None, b"1"])
def test_chunked_or_underdeclared_body_stops_at_limit(declared):
    async def exercise():
        calls = 0

        async def receive():
            nonlocal calls
            calls += 1
            assert calls <= 3, "Oversized stream must not be drained into memory"
            return {
                "type": "http.request",
                "body": b"x" * (contract()["x-max-json-body-bytes"] // 2),
                "more_body": True,
            }

        headers = [(b"content-type", b"application/json")]
        if declared is not None:
            headers.append((b"content-length", declared))
        request = Request({"type": "http", "headers": headers}, receive)
        with pytest.raises(PayloadTooLarge):
            await read_body(request)
        assert calls == 3

    asyncio.run(exercise())


def test_declared_oversized_body_is_rejected_before_receiving():
    async def exercise():
        async def receive():
            pytest.fail("Oversized Content-Length must be rejected without reading")

        request = Request(
            {
                "type": "http",
                "headers": [
                    (b"content-type", b"application/json"),
                    (
                        b"content-length",
                        str(contract()["x-max-json-body-bytes"] + 1).encode(),
                    ),
                ],
            },
            receive,
        )
        with pytest.raises(PayloadTooLarge):
            await read_body(request)

    asyncio.run(exercise())


def test_json_at_the_size_limit_is_accepted(app):
    body = b'{"token":"x"}'
    body += b" " * (contract()["x-max-json-body-bytes"] - len(body))
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/auth/login",
                content=body,
                headers={"Content-Type": "application/json"},
            ).status_code
            == 410
        )


def test_deep_json_is_rejected_without_server_error(app):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            content=b"[" * 2000 + b"]" * 2000,
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 400
