from __future__ import annotations
import json
from os import getenv
from typing import Callable, Dict, List, Optional, Tuple, TypeVar
from flask import Flask, request, jsonify, Request, send_file, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from collections import defaultdict
from datetime import datetime, timedelta
import argparse
from uuid import uuid4
from server_browser_backend import dict_util
from server_browser_backend.server_list import (
    InvalidSecretKey,
    SecretKeyMissing,
    ServerList
)

from server_browser_backend.models import UpdateRegisteredServer, Server
from server_browser_backend.dict_util import DictKeyError, DictTypeError
from server_browser_backend import tbio
from server_browser_backend import playfab
from server_browser_backend import routes
from logging.config import dictConfig

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
    parser.add_argument(
        "--ban-list",
        type=str,
        default="ban_list.txt",
        help="File location of line separated list of banned IPs",
    )
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


    ban_list_location = args.ban_list

    if getenv("ADMIN_KEY") is None:
        print("WARNING: ADMIN_KEY environment variable not set. Admin routes disabled.")

    try:
        with open(ban_list_location) as f:
            routes.ban_list.extend(f.read().splitlines())
    except FileNotFoundError:
        print(
            f"WARNING: Ban list file {ban_list_location} not found. Creating empty ban list file."
        )
        with open(ban_list_location, "w") as f:
            f.write("[]")

    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
