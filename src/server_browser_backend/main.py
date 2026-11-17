from __future__ import annotations

import logging
import secrets
from os import environ
from pathlib import Path

from server_browser_backend.application import Application
from server_browser_backend.auth.account_digests import AccountDigester
from server_browser_backend.auth.eos_identity import EosConnectVerifier
from server_browser_backend.auth.game_accounts import GameAccountStore
from server_browser_backend.auth.game_identity import PlayFabIdentityVerifier
from server_browser_backend.auth.game_join import GameJoinService
from server_browser_backend.auth.game_join_tickets import GameJoinTicketStore
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
    server_list = ServerList(
        heartbeat_timeout=65,
        max_servers=int(environ.get("MAX_REGISTERED_SERVERS", "1024")),
        max_servers_per_ip=int(environ.get("MAX_REGISTERED_SERVERS_PER_IP", "16")),
    )
    ban_list = IpList(admin_key, str(config_dir / "ban_list.txt"))
    verified_list = IpList(admin_key, str(config_dir / "verified_list.txt"))
    policy = RequestPolicy(ban_list, verified_list)
    ticket_path = environ.get("GAME_JOIN_TICKET_DATABASE")
    verifier_session = environ.get("GAME_JOIN_VERIFIER_SESSION_TICKET")
    audience = environ.get("GAME_JOIN_AUDIENCE")
    game_signing_path = environ.get("GAME_JOIN_SIGNING_KEYRING")
    game_signing = SigningKeys(Path(game_signing_path)) if game_signing_path else None
    account_path = environ.get("GAME_ACCOUNT_DATABASE")
    if game_signing and not account_path:
        raise ValueError(
            "Signed game admission requires persistent GAME_ACCOUNT_DATABASE"
        )
    account_key_path = environ.get("GAME_ACCOUNT_HMAC_KEY_FILE")
    if game_signing and not account_key_path:
        raise ValueError("Signed game admission requires GAME_ACCOUNT_HMAC_KEY_FILE")
    eos_settings = {
        name: environ.get(variable, "")
        for name, variable in {
            "issuer": "EOS_CONNECT_ISSUER",
            "client_id": "EOS_CONNECT_CLIENT_ID",
            "product_id": "EOS_CONNECT_PRODUCT_ID",
            "sandbox_id": "EOS_CONNECT_SANDBOX_ID",
            "deployment_id": "EOS_CONNECT_DEPLOYMENT_ID",
        }.items()
    }
    if (game_signing or any(eos_settings.values())) and not all(eos_settings.values()):
        raise ValueError(
            "Signed game admission requires all pinned EOS Connect trust settings"
        )
    eos = (
        EosConnectVerifier(
            issuer=eos_settings["issuer"],
            client_id=eos_settings["client_id"],
            product_id=eos_settings["product_id"],
            sandbox_id=eos_settings["sandbox_id"],
            deployment_id=eos_settings["deployment_id"],
        )
        if game_signing
        else None
    )
    if (ticket_path or game_signing) and (not verifier_session or not audience):
        raise ValueError(
            "Game join validation requires an independent verifier session and GAME_JOIN_AUDIENCE"
        )
    game_join = (
        GameJoinService(
            server_list,
            PlayFabIdentityVerifier(verifier_session or ""),
            GameJoinTicketStore(Path(ticket_path)) if ticket_path else None,
            audience or "",
            eos=eos,
            signing=game_signing,
            accounts=(
                GameAccountStore(
                    Path(account_path), AccountDigester.load(Path(account_key_path))
                )
                if game_signing and account_path and account_key_path
                else None
            ),
        )
        if ticket_path or game_signing
        else None
    )
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
            game_join=game_join,
            game_signing_keys=game_signing,
        ),
        CompatibilityApi(
            server_list=server_list, policy=policy, motd_directory=motd_directory
        ),
        debug_mode=debug_mode,
        trusted_proxies=tuple(
            value.strip()
            for value in environ.get(
                "TRUSTED_PROXY_CIDRS", "127.0.0.1/32,::1/128"
            ).split(",")
            if value.strip()
        ),
    )
    logger.info(
        "Backend services initialized config_dir=%r heartbeat_timeout_seconds=%s debug_mode=%s",
        str(config_dir),
        server_list.heartbeat_timeout,
        debug_mode,
    )
    return application


app = create_default_app()
