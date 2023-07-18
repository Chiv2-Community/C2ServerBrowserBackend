from __future__ import annotations

from logging.config import dictConfig

from flask import Flask

from server_browser_backend import routes

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

app = Flask(__name__)

app.register_blueprint(routes.playfab_bp)
app.register_blueprint(routes.tbio_bp)
app.register_blueprint(routes.api_v1_bp)
