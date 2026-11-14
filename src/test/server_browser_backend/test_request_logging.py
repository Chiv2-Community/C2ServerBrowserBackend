"""IP context follows requests across async work, threads, and error handling."""

import asyncio
import logging

import httpx
from anyio import to_thread

from server_browser_backend.request_logging import ConsoleFormatter, request_scope


def test_request_ip_context_is_isolated_and_reset(app):
    messages = []

    class Capture(logging.Handler):
        def emit(self, record):
            messages.append(self.format(record))

    handler = Capture()
    handler.setFormatter(ConsoleFormatter("%(requestor_ip)s | %(name)s - %(message)s"))
    logger = logging.getLogger("server_browser_backend.request_logging_probe")
    logger.addHandler(handler)
    previous_level = logger.level
    logger.setLevel(logging.INFO)

    @app.get("/logging-probe/{label}")
    async def probe(label: str):
        logger.info("%s before", label)
        await asyncio.sleep(0.01)
        await to_thread.run_sync(lambda: logger.info("%s thread", label))
        logger.info("%s after", label)
        return {}

    async def exercise():
        async def request(label, forwarded=None):
            async def send(scope_message):
                # Uvicorn emits access logs while handling response.start.
                if scope_message["type"] == "http.response.start":
                    logger.info("%s access", label)

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": f"/logging-probe/{label}",
                "raw_path": f"/logging-probe/{label}".encode(),
                "query_string": b"",
                "headers": (
                    []
                    if forwarded is None
                    else [(b"x-forwarded-for", forwarded.encode())]
                ),
                "client": ("127.0.0.1", 1234),
                "server": ("test", 80),
            }
            await app(scope, receive, send)
            assert request_scope.get() is None

        await asyncio.gather(
            request("v4", "192.0.2.4"),
            request("v6", "2001:db8::6"),
            request("direct"),
            request("invalid", "not-an-ip"),
        )

    try:
        asyncio.run(exercise())
        logger.info("outside")
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
    for label, ip in (
        ("v4", "192.0.2.4"),
        ("v6", "2001:db8::6"),
        ("direct", "127.0.0.1"),
        ("invalid", "-"),
    ):
        for event in ("before", "thread", "after", "access"):
            assert f"{ip} | {logger.name} - {label} {event}" in messages
    assert messages[-1] == f"- | {logger.name} - outside"


def test_unhandled_error_retains_forwarded_ip(app, browser, monkeypatch, caplog):
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

    class Capture(logging.Handler):
        def emit(self, record):
            messages.append(self.format(record))

    messages = []
    handler = Capture()
    handler.setFormatter(ConsoleFormatter("%(requestor_ip)s | %(message)s"))
    logger = logging.getLogger("server_browser_backend.error_handlers")
    logger.addHandler(handler)
    try:
        asyncio.run(exercise())
    finally:
        logger.removeHandler(handler)
    assert len(messages) == 1
    assert messages[0].startswith("192.0.2.8 | Unhandled exception")
