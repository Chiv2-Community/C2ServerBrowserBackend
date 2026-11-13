"""Exercise production logging in fresh interpreters, outside pytest's log setup."""

import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("admin_configured", [False, True])
@pytest.mark.parametrize("uvicorn_level", ["info", "warning"])
def test_app_import_preserves_uvicorn_and_preexisting_loggers(
    tmp_path, admin_configured, uvicorn_level
):
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"GRAYLOG_HOST", "GRAYLOG_PORT", "ADMIN_KEY", "DEBUG_MODE"}
    }
    environment["CONFIG_DIR"] = str(tmp_path)
    environment["TEST_UVICORN_LOG_LEVEL"] = uvicorn_level
    if admin_configured:
        environment["ADMIN_KEY"] = "private-admin-key-do-not-log"
    code = """
import logging
import os
import uvicorn
uvicorn.Config("server_browser_backend.main:app", log_level=os.environ["TEST_UVICORN_LOG_LEVEL"]).configure_logging()
names = ("uvicorn", "uvicorn.error", "uvicorn.access")
handlers = {name: list(logging.getLogger(name).handlers) for name in names}
levels = {name: logging.getLogger(name).level for name in names}
application_logger = logging.getLogger("server_browser_backend.routes.api_v1")
import server_browser_backend.main
for name in names:
    logger = logging.getLogger(name)
    assert not logger.disabled, name
    assert logger.handlers == handlers[name], name
    assert logger.level == levels[name], name
assert not application_logger.disabled
logging.getLogger("uvicorn.error").warning("STARTUP-PROBE")
logging.getLogger("uvicorn.access").warning('%s - "%s %s HTTP/%s" %d', "127.0.0.1:1", "GET", "/api/v1/servers", "1.1", 200)
application_logger.warning("APPLICATION-PROBE")
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
    assert output.count("GET /api/v1/servers HTTP/1.1") == 1
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
