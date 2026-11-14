"""Reject JSON values that cannot be handled safely after decoding."""

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from server_browser_fastapi.runtime import JsonMissing, read_body
from server_browser_models.runtime import contract
from starlette.requests import Request


def test_deep_invalid_body_does_not_log_credentials(app, caplog):
    nested: object = "leaf"
    for _ in range(300):
        nested = [nested]
    body = {"token": {"secret": "credential-sentinel", "nested": nested}}
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/auth/login",
            content=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 400
    assert "credential-sentinel" not in caplog.text
    assert "Unhandled exception" not in caplog.text


@pytest.mark.parametrize(
    "body",
    [
        {"token": {"secret": "credential-sentinel", "value": "\ud800"}},
        {"token": {"\udc00": "credential-sentinel"}},
    ],
)
def test_unpaired_surrogates_do_not_break_error_responses_or_log_credentials(
    app, caplog, body
):
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/api/v1/auth/login",
            content=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 400
    assert "credential-sentinel" not in caplog.text
    assert "Unhandled exception" not in caplog.text


@pytest.mark.parametrize("depth,expected", [(64, 410), (65, 400)])
def test_json_depth_boundary(app, depth, expected):
    nested: object = "leaf"
    for _ in range(depth - 1):
        nested = [nested]
    body = {"token": "sentinel", "extra": nested}
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            content=json.dumps(body),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == expected


@pytest.mark.parametrize("trickle", [False, True])
@pytest.mark.parametrize("known_length", [False, True])
def test_slow_json_upload_has_a_total_deadline(
    app, monkeypatch, caplog, trickle, known_length
):
    monkeypatch.setitem(contract(), "x-json-body-timeout-seconds", 0.04)

    async def exercise():
        closed = asyncio.Event()

        async def body():
            try:
                yield b'{"name":"credential-sentinel'
                if trickle:
                    while True:
                        await asyncio.sleep(0.002)
                        yield b"x"
                else:
                    await asyncio.Event().wait()
            finally:
                closed.set()

        headers = {"Content-Type": "application/json"}
        if known_length:
            headers["Content-Length"] = str(contract()["x-max-json-body-bytes"])
        transport = httpx.ASGITransport(app=app, client=("127.0.0.1", 1234))
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await asyncio.wait_for(
                client.post("/api/v1/servers", content=body(), headers=headers),
                timeout=0.5,
            )
        assert response.status_code == 408
        assert response.json()["status"] == "request_timeout"
        assert response.headers["connection"] == "close"
        assert closed.is_set()

    asyncio.run(exercise())
    assert app.browser_api.server_list.get_all() == []
    assert "credential-sentinel" not in caplog.text
    assert "Unhandled exception" not in caplog.text


def test_normal_chunked_json_upload_still_succeeds(app):
    async def exercise():
        async def body():
            yield b'{"token":'
            await asyncio.sleep(0.001)
            yield b'"sentinel"}'

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/login",
                content=body(),
                headers={"Content-Type": "application/json"},
            )
        assert response.status_code == 410

    asyncio.run(exercise())


def test_disconnected_json_upload_is_not_an_internal_error():
    async def exercise():
        async def receive():
            return {"type": "http.disconnect"}

        request = Request(
            {"type": "http", "headers": [(b"content-type", b"application/json")]},
            receive,
        )
        with pytest.raises(JsonMissing):
            await read_body(request)

    asyncio.run(exercise())


def test_upload_cancellation_stops_the_receive_task():
    async def exercise():
        started = asyncio.Event()
        stopped = asyncio.Event()

        async def receive():
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        request = Request(
            {"type": "http", "headers": [(b"content-type", b"application/json")]},
            receive,
        )
        task = asyncio.create_task(read_body(request))
        await asyncio.wait_for(started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stopped.is_set()

    asyncio.run(exercise())
