"""Exercise production logging in fresh interpreters, outside pytest's log setup."""

import os
import re
import subprocess
import sys

import pytest


@pytest.mark.parametrize("admin_configured", [False, True])
@pytest.mark.parametrize("uvicorn_level", ["info", "warning"])
@pytest.mark.parametrize("access_log", [False, True])
def test_app_import_preserves_uvicorn_and_preexisting_loggers(
    tmp_path, admin_configured, uvicorn_level, access_log
):
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"GRAYLOG_HOST", "GRAYLOG_PORT", "ADMIN_KEY", "DEBUG_MODE"}
    }
    environment["CONFIG_DIR"] = str(tmp_path)
    environment["TEST_UVICORN_LOG_LEVEL"] = uvicorn_level
    environment["TEST_ACCESS_LOG"] = str(access_log)
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
logging.getLogger("uvicorn.error").info("UVICORN-INFO-PROBE")
"""
    process = subprocess.run(
        [sys.executable, "-c", code],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    output = process.stdout + process.stderr
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
    assert f" | WARNING | {'-':<15} | uvicorn.error - STARTUP-PROBE" in output
    for line in output.splitlines():
        assert re.fullmatch(
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \| (?:INFO |WARNING|ERROR) \| - {14} \| [\w.]+ - .*",
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
    process = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    assert process.stderr.count("GRAYLOG-PROBE") == 1


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
    process = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    lines = process.stderr.splitlines()
    assert len(lines) == 2
    for line, ip in zip(lines, ("192.0.2.1", "2001:db8:1234:5678:abcd:1234:5678:abcd")):
        assert f" | INFO  | {ip:<15} | uvicorn.access - IP-PROBE" in line
