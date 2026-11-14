"""IP context follows requests across async work, threads, and error handling."""

import asyncio
import logging
from contextlib import contextmanager

import httpx
import pytest
from anyio import to_thread

from server_browser_backend.request_logging import ConsoleFormatter, request_scope


@contextmanager
def capture_logs(logger):
    messages = []

    class Capture(logging.Handler):
        def emit(self, record):
            messages.append(self.format(record))

    handler = Capture()
    handler.setFormatter(ConsoleFormatter("%(requestor_ip)s | %(name)s - %(message)s"))
    logger.addHandler(handler)
    previous_level = logger.level
    logger.setLevel(logging.INFO)
    try:
        yield messages
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        handler.close()


def test_request_ip_context_is_isolated_and_reset(app):
    logger = logging.getLogger("server_browser_backend.request_logging_probe")

    @app.get("/logging-probe/{label}")
    async def probe(label: str):
        logger.info("%s before", label)
        await asyncio.sleep(0.01)
        await to_thread.run_sync(lambda: logger.info("%s thread", label))
        logger.info("%s after", label)
        return {}

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:

            async def request(label, forwarded=None):
                headers = {} if forwarded is None else {"X-Forwarded-For": forwarded}
                response = await client.get(f"/logging-probe/{label}", headers=headers)
                assert response.status_code == 200
                assert request_scope.get() is None

            await asyncio.gather(
                request("v4", "192.0.2.4"),
                request("v6", "2001:db8::6"),
                request("direct"),
                request("invalid", "not-an-ip"),
            )

    with capture_logs(logger) as messages:
        asyncio.run(exercise())
        logger.info("outside")
    for label, ip in (
        ("v4", "192.0.2.4"),
        ("v6", "2001:db8::6"),
        ("direct", "127.0.0.1"),
        ("invalid", "127.0.0.1"),
    ):
        for event in ("before", "thread", "after"):
            assert f"{ip} | {logger.name} - {label} {event}" in messages
    assert messages[-1] == f"- | {logger.name} - outside"


def test_unhandled_error_retains_forwarded_ip(app, browser, monkeypatch):
    def fail():
        raise RuntimeError("logging probe failure")

    monkeypatch.setattr(browser.server_list, "get_all", fail)

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            assert (
                await client.get(
                    "/api/v1/servers", headers={"X-Forwarded-For": "192.0.2.8"}
                )
            ).status_code == 500
        assert request_scope.get() is None

    logger = logging.getLogger("server_browser_backend.error_handlers")
    with capture_logs(logger) as messages:
        asyncio.run(exercise())
    assert len(messages) == 1
    assert messages[0].startswith(f"192.0.2.8 | {logger.name} - Unhandled exception")


def test_cancellation_preserves_exception_identity_and_resets_context(app):
    cancellation = asyncio.CancelledError("cancellation probe")

    @app.get("/cancel-probe")
    async def cancel():
        raise cancellation

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            with pytest.raises(asyncio.CancelledError) as caught:
                await client.get(
                    "/cancel-probe", headers={"X-Forwarded-For": "192.0.2.9"}
                )
        assert caught.value is cancellation
        assert getattr(cancellation, "_request_log_ip") == "192.0.2.9"
        assert request_scope.get() is None

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "address, expected",
    [
        ("192.0.2.8:0", "192.0.2.8"),
        (
            "2001:0db8:1234:5678:abcd:1234:5678:abcd:0",
            "2001:db8:1234:5678:abcd:1234:5678:abcd",
        ),
        ("not-an-ip:0", "-"),
        ("", "-"),
    ],
)
def test_access_fallback_normalizes_existing_client_argument(address, expected):
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        0,
        '%s - "%s %s HTTP/%s" %d',
        (address, "GET", "/", "1.1", 500),
        None,
    )
    formatter = ConsoleFormatter("%(requestor_ip)s | %(message)s")
    assert formatter.format(record).startswith(f"{expected} | ")
    assert record.args == (address, "GET", "/", "1.1", 500)
    token = request_scope.set({"client": ("192.0.2.10", 0)})
    try:
        assert formatter.format(record).startswith("192.0.2.10 | ")
    finally:
        request_scope.reset(token)
