from __future__ import annotations

from logging.config import dictConfig

from pygelf import GelfTcpHandler
from os import environ
import logging

import secrets
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa

from server_browser_backend.application import Application
from server_browser_backend.env import show_registered_ips
from server_browser_backend.ip_list import IpList
from server_browser_backend.routes.api_v1 import BrowserApi
from server_browser_backend.routes.chiv2_compat import CompatibilityApi
from server_browser_backend.routes.shared import RequestPolicy
from server_browser_backend.server_list import ServerList
from server_browser_backend.token_reissuer import TokenReissuer
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
            "stderr": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["stderr"]},
    }
)

graylog_host = environ.get("GRAYLOG_HOST", None)
graylog_port = int(environ.get("GRAYLOG_PORT", 12201))

if graylog_host is not None:
    logger.info(f"Logging to Graylog at {graylog_host}:{graylog_port} with level INFO")
    graylog_handler = GelfTcpHandler(host=graylog_host, port=graylog_port, include_extra_fields=True)
    graylog_handler.setLevel(logging.INFO)
    logger.addHandler(graylog_handler)


def create_default_app() -> Application:
    """Composition root: read configuration and construct one shared service graph."""
    admin_key = environ.get("ADMIN_KEY", secrets.token_urlsafe(128))
    config_dir = Path(environ.get("CONFIG_DIR", "config"))
    server_list = ServerList(heartbeat_timeout=65)
    ban_list = IpList(admin_key, str(config_dir / "ban_list.txt"))
    verified_list = IpList(admin_key, str(config_dir / "verified_list.txt"))
    policy = RequestPolicy(ban_list, verified_list)
    token_reissuer = TokenReissuer(
        private_key=rsa.generate_private_key(public_exponent=65537, key_size=2048),
        kid="server-browser-backend-key-1",
        eos_jwks="https://api.epicgames.dev/epic/oauth/v2/.well-known/jwks.json",
        expected_audience=environ.get("EOS_AUDIENCE", "7f2b13acf2e84ab0ae8604d822f10498"),
        issuer=environ.get("SERVER_BROWSER_FQDN", "chivalry2-server-browser-backend"),
    )
    motd_directory = Path(__file__).resolve().parent / "assets/motd"
    if not motd_directory.exists():
        motd_directory = Path(__file__).resolve().parents[2] / "assets/motd"
    return Application(
        BrowserApi(
            server_list=server_list, ban_list=ban_list, verified_list=verified_list,
            policy=policy, token_reissuer=token_reissuer, show_registered_ips=show_registered_ips,
        ),
        CompatibilityApi(server_list=server_list, policy=policy, motd_directory=motd_directory),
        debug_mode=environ.get("DEBUG_MODE", "false").lower() == "true",
    )


app = create_default_app()
