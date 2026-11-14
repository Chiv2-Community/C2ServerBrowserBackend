from __future__ import annotations

import logging
import secrets
from os import environ
from pathlib import Path

from server_browser_backend.application import Application
from server_browser_backend.auth.signing import SigningKeys
from server_browser_backend.env import show_registered_ips
from server_browser_backend.ip_list import IpList
from server_browser_backend.logging_config import configure_logging
from server_browser_backend.routes.api_v1 import BrowserApi
from server_browser_backend.routes.chiv2_compat import CompatibilityApi
from server_browser_backend.routes.shared import RequestPolicy
from server_browser_backend.server_list import ServerList

logger = logging.getLogger(__name__)

configure_logging(
    graylog_host=environ.get("GRAYLOG_HOST"),
    graylog_port=int(environ.get("GRAYLOG_PORT", 12201)),
)


def create_default_app() -> Application:
    """Composition root: read configuration and construct one shared service graph."""
    admin_key = environ.get("ADMIN_KEY", secrets.token_urlsafe(128))
    if "ADMIN_KEY" not in environ:
        logger.warning(
            "ADMIN_KEY is not configured; using a generated process-local admin key"
        )
    config_dir = Path(environ.get("CONFIG_DIR", "config"))
    server_list = ServerList(heartbeat_timeout=65)
    ban_list = IpList(admin_key, str(config_dir / "ban_list.txt"))
    verified_list = IpList(admin_key, str(config_dir / "verified_list.txt"))
    policy = RequestPolicy(ban_list, verified_list)
    signing_path = environ.get("DISCORD_SIGNING_KEYRING")
    signing_keys = SigningKeys(Path(signing_path)) if signing_path is not None else None
    if signing_keys is None:
        logger.info(
            "Discord signing is unconfigured; no join verification keys are published"
        )
    motd_directory = Path(__file__).resolve().parent / "assets/motd"
    if not motd_directory.exists():
        motd_directory = Path(__file__).resolve().parents[2] / "assets/motd"
    debug_mode = environ.get("DEBUG_MODE", "false").lower() == "true"
    application = Application(
        BrowserApi(
            server_list=server_list,
            ban_list=ban_list,
            verified_list=verified_list,
            policy=policy,
            signing_keys=signing_keys,
            show_registered_ips=show_registered_ips,
        ),
        CompatibilityApi(
            server_list=server_list, policy=policy, motd_directory=motd_directory
        ),
        debug_mode=debug_mode,
    )
    logger.info(
        "Backend services initialized config_dir=%r heartbeat_timeout_seconds=%s debug_mode=%s",
        str(config_dir),
        server_list.heartbeat_timeout,
        debug_mode,
    )
    return application


app = create_default_app()
