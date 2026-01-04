from __future__ import annotations

from logging.config import dictConfig

from pygelf import GelfTcpHandler
from os import environ
import logging

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from server_browser_backend import routes
logger = logging.getLogger()

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s: %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://flask.logging.wsgi_errors_stream",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["wsgi"]},
    }
)

graylog_host = environ.get("GRAYLOG_HOST", None)
graylog_port = int(environ.get("GRAYLOG_PORT", 12201))

if graylog_host is not None:
    logger.info(f"Logging to Graylog at {graylog_host}:{graylog_port} with level INFO")
    graylog_handler = GelfTcpHandler(host=graylog_host, port=graylog_port, include_extra_fields=True)
    graylog_handler.setLevel(logging.INFO)
    logger.addHandler(graylog_handler)


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

app.register_blueprint(routes.playfab_bp)
app.register_blueprint(routes.tbio_bp)
app.register_blueprint(routes.api_v1_bp)

