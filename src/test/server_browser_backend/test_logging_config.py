"""Exercise production logging in fresh interpreters, outside pytest's log setup."""

import os
import re
import subprocess
import sys

import pytest


def run_python(code, **environment):
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"GRAYLOG_HOST", "GRAYLOG_PORT", "ADMIN_KEY", "DEBUG_MODE"}
    }
    env.update(environment)
    process = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    return process.stdout + process.stderr


@pytest.mark.parametrize("admin_configured", [False, True])
@pytest.mark.parametrize("uvicorn_level", ["info", "warning"])
@pytest.mark.parametrize("access_log", [False, True])
def test_app_import_preserves_uvicorn_and_preexisting_loggers(
    tmp_path, admin_configured, uvicorn_level, access_log
):
    environment = {
        "CONFIG_DIR": str(tmp_path),
        "TEST_UVICORN_LOG_LEVEL": uvicorn_level,
        "TEST_ACCESS_LOG": str(access_log),
    }
    if admin_configured:
        environment["ADMIN_KEY"] = "private-admin-key-do-not-log"
    code = """
import logging
import os
import uvicorn
uvicorn.Config("server_browser_backend.main:app", log_level=os.environ["TEST_UVICORN_LOG_LEVEL"], access_log=os.environ["TEST_ACCESS_LOG"] == "True").configure_logging()
names = ("uvicorn", "uvicorn.error", "uvicorn.access")
handlers = {name: list(logging.getLogger(name).handlers) for name in names}
levels = {name: logging.getLogger(name).level for name in names}
propagation = {name: logging.getLogger(name).propagate for name in names}
application_logger = logging.getLogger("server_browser_backend.routes.api_v1")
import server_browser_backend.main
for name in names:
    logger = logging.getLogger(name)
    assert not logger.disabled, name
    assert logger.handlers == handlers[name], name
    assert logger.level == levels[name], name
    assert logger.propagate == propagation[name], name
assert not application_logger.disabled
logging.getLogger("uvicorn.error").warning("STARTUP-PROBE")
logging.getLogger("uvicorn.access").info('%s - "%s %s HTTP/%s" %d', "127.0.0.1:1", "GET", "/api/v1/servers", "1.1", 200)
application_logger.warning("APPLICATION-PROBE")
application_logger.info("INFO-PROBE")
application_logger.error("ERROR-PROBE")
application_logger.critical("CRITICAL-PROBE")
logging.getLogger("uvicorn.error").info("UVICORN-INFO-PROBE")
"""
    output = run_python(code, **environment)
    assert output.count("STARTUP-PROBE") == 1
    assert output.count("APPLICATION-PROBE") == 1
    assert output.count("GET /api/v1/servers HTTP/1.1") == int(
        access_log and uvicorn_level == "info"
    )
    assert output.count("UVICORN-INFO-PROBE") == int(uvicorn_level == "info")
    assert (
        f" | INFO  | {'-':<15} | server_browser_backend.routes.api_v1 - INFO-PROBE"
        in output
    )
    assert (
        f" | ERROR | {'-':<15} | server_browser_backend.routes.api_v1 - ERROR-PROBE"
        in output
    )
    assert f" | WARNI | {'-':<15} | uvicorn.error - STARTUP-PROBE" in output
    assert f" | CRITI | {'-':<15} | server_browser_backend.routes.api_v1 - CRITICAL-PROBE" in output
    for line in output.splitlines():
        ip = "127.0.0.1" if " | uvicorn.access - " in line else "-"
        assert re.fullmatch(
            rf"\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}},\d{{3}} \| (?:INFO |WARNI|ERROR|CRITI) \| {re.escape(f'{ip:<15}')} \| [\w.]+ - .*",
            line,
        ), line
    assert "Backend services initialized" in output
    assert ("ADMIN_KEY is not configured" in output) is (not admin_configured)
    assert "private-admin-key-do-not-log" not in output


def test_graylog_and_console_receive_application_events_once():
    code = """
import logging
from unittest.mock import patch
from server_browser_backend.logging_config import configure_logging

events = []
instances = []
class GraylogProbe(logging.Handler):
    def __init__(self, **settings):
        super().__init__()
        self.settings = settings
        instances.append(self)
    def emit(self, record):
        events.append(record.getMessage())

with patch("server_browser_backend.logging_config.GelfTcpHandler", GraylogProbe):
    configure_logging(graylog_host="graylog.internal", graylog_port=12202)
    configure_logging(graylog_host="graylog.internal", graylog_port=12202)
    logging.getLogger("server_browser_backend.routes.api_v1").info("GRAYLOG-PROBE")
assert len(logging.getLogger().handlers) == 2
assert instances[-1].settings == {"host": "graylog.internal", "port": 12202, "include_extra_fields": True}
assert events.count("GRAYLOG-PROBE") == 1
"""
    assert run_python(code).count("GRAYLOG-PROBE") == 1


def test_console_ip_padding_preserves_long_ipv6_addresses():
    code = """
import logging
from server_browser_backend.logging_config import configure_logging
from server_browser_backend.request_logging import request_scope
configure_logging()
for ip in ("192.0.2.1", "2001:db8:1234:5678:abcd:1234:5678:abcd"):
    token = request_scope.set({"client": (ip, 1234)})
    try:
        logging.getLogger("uvicorn.access").info("IP-PROBE")
    finally:
        request_scope.reset(token)
"""
    lines = run_python(code).splitlines()
    assert len(lines) == 2
    for line, ip in zip(lines, ("192.0.2.1", "2001:db8:1234:5678:abcd:1234:5678:abcd")):
        assert f" | INFO  | {ip:<15} | uvicorn.access - IP-PROBE" in line


@pytest.mark.parametrize("cancel_on_shutdown", [False, True])
def test_real_uvicorn_unhandled_errors_keep_ip_without_leaking_context(
    tmp_path, cancel_on_shutdown
):
    code = """
import asyncio
import logging
import os
import queue
import socket
import threading
import httpx
import uvicorn

async def main():
    cancel = os.environ["CANCEL_ON_SHUTDOWN"] == "True"
    config = uvicorn.Config("server_browser_backend.main:app", proxy_headers=False, lifespan="off", timeout_graceful_shutdown=0.01)
    config.load()
    from server_browser_backend.main import app
    from server_browser_backend.request_logging import request_scope

    started = queue.Queue()
    release = threading.Event()
    def fail():
        logging.getLogger("server_browser_backend.probe").info("SYNC-PROBE")
        if cancel:
            started.put(True)
            assert release.wait(10), "workers were not released"
            return []
        raise RuntimeError("HTTP-FAILURE-PROBE")

    app.browser_api.server_list.get_all = fail
    application = config.loaded_app
    async def boundary(scope, receive, send):
        try:
            await application(scope, receive, send)
        finally:
            assert request_scope.get() is None
            logging.getLogger("uvicorn.error").warning("AFTER-ASGI-PROBE")
    config.loaded_app = boundary
    server = uvicorn.Server(config)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        task = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            while not server.started:
                await asyncio.sleep(0.01)
            async with httpx.AsyncClient() as client:
                requests = asyncio.gather(*(
                    client.get(
                        f"http://127.0.0.1:{sock.getsockname()[1]}/api/v1/servers",
                        headers={"X-Forwarded-For": "198.51.100.1, " + ip},
                    )
                    for ip in ("192.0.2.8", "2001:db8:1234:5678:abcd:1234:5678:abcd")
                ))
                if cancel:
                    async def wait_for_workers():
                        while started.qsize() != 2:
                            await asyncio.sleep(0.01)
                    await asyncio.wait_for(wait_for_workers(), timeout=5)
                    server.should_exit = True
                    await task
                responses = await requests
                assert all(response.status_code == 500 for response in responses)
        finally:
            release.set()
            server.should_exit = True
            await task
        logging.getLogger("uvicorn.error").warning("OUTSIDE-PROBE")

asyncio.run(main())
"""
    output = run_python(
        code, CONFIG_DIR=str(tmp_path), CANCEL_ON_SHUTDOWN=str(cancel_on_shutdown)
    )
    lines = output.splitlines()
    for ip in ("192.0.2.8", "2001:db8:1234:5678:abcd:1234:5678:abcd"):
        expected = [
            ("INFO", "server_browser_backend.probe", "SYNC-PROBE"),
            ("INFO", "uvicorn.access", f'{ip}:0 - "GET /api/v1/servers HTTP/1.1" 500'),
            ("ERROR", "uvicorn.error", "Exception in ASGI application"),
        ]
        if not cancel_on_shutdown:
            expected.append(
                (
                    "ERROR",
                    "server_browser_backend.error_handlers",
                    "Unhandled exception",
                )
            )
        for level, namespace, message in expected:
            matching = [
                line
                for line in lines
                if f" | {level:<5} | {ip:<15} | {namespace} - {message}" in line
            ]
            assert len(matching) == 1, output
            assert re.match(
                r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \| ", matching[0]
            )
    if cancel_on_shutdown:
        assert (
            output.count(
                "asyncio.exceptions.CancelledError: Task cancelled, timeout graceful shutdown exceeded"
            )
            == 2
        )
        assert "Unhandled exception" not in output
    for marker, count in (("AFTER-ASGI-PROBE", 2), ("OUTSIDE-PROBE", 1)):
        assert (
            sum(
                f" | WARNI | {'-':<15} | uvicorn.error - {marker}" in line
                for line in lines
            )
            == count
        ), output
