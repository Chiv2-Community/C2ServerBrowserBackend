"""Unify console formatting without replacing ASGI loggers or their levels."""

import logging
from logging.config import dictConfig

from pygelf import GelfTcpHandler

from server_browser_backend.request_logging import ConsoleFormatter


def configure_logging(
    *, graylog_host: str | None = None, graylog_port: int = 12201
) -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": ConsoleFormatter,
                    "format": "%(asctime)s | %(levelname)-5s | %(requestor_ip)-15s | %(name)s - %(message)s",
                },
            },
            "handlers": {
                "stderr": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                    "formatter": "default",
                },
            },
            "root": {"level": "INFO", "handlers": ["stderr"]},
        }
    )
    # Uvicorn owns these handlers and levels; only replace their formatters.
    formatter = logging.getLogger().handlers[0].formatter
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        for handler in logging.getLogger(name).handlers:
            handler.setFormatter(formatter)
    if graylog_host is not None:
        handler = GelfTcpHandler(
            host=graylog_host,
            port=graylog_port,
            include_extra_fields=True,
        )
        handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(handler)
        logging.getLogger(__name__).info(
            "Graylog logging enabled host=%r port=%s", graylog_host, graylog_port
        )
