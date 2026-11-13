"""Configure application logging without replacing the ASGI server's loggers."""

import logging
from logging.config import dictConfig

from pygelf import GelfTcpHandler


def configure_logging(
    *, graylog_host: str | None = None, graylog_port: int = 12201
) -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
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
