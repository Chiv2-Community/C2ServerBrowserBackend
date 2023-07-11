from __future__ import annotations

import argparse
from logging.config import dictConfig

from flask import Flask

from server_browser_backend import routes

app = Flask(__name__)

app.register_blueprint(routes.playfab_bp)
app.register_blueprint(routes.tbio_bp)
app.register_blueprint(routes.api_v1_bp)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the Flask server.")
    parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="The interface to bind to."
    )
    parser.add_argument("--port", type=int, default=8080, help="The port to bind to.")
    args = parser.parse_args()

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

    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
