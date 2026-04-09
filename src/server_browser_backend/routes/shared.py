import os
import secrets
from flask import request
from cryptography.hazmat.primitives.asymmetric import rsa
from server_browser_backend.ip_list import IpList
from server_browser_backend.server_list import SecretKeyMissing, ServerList
from server_browser_backend.token_reissuer import TokenReissuer

from typing import Any, Dict

class JsonMissing(Exception):
    pass

ADMIN_KEY = os.environ.get("ADMIN_KEY", secrets.token_urlsafe(128))
CONFIG_DIR = os.environ.get("CONFIG_DIR", "config")

DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"

ADMIN_KEY_HEADER = "x-chiv2-server-browser-admin-key"
KEY_HEADER = "x-chiv2-server-browser-key"

heartbeat_timeout = 65
server_list: ServerList = ServerList(heartbeat_timeout)

ban_list: IpList = IpList(ADMIN_KEY, f"{CONFIG_DIR}/ban_list.txt")
verified_list: IpList = IpList(ADMIN_KEY, f"{CONFIG_DIR}/verified_list.txt")

# Setup TokenReissuer
EOS_JWKS_URL = "https://api.epicgames.dev/epic/oauth/v2/.well-known/jwks.json"
EOS_AUDIENCE = os.environ.get("EOS_AUDIENCE", "7f2b13acf2e84ab0ae8604d822f10498")
SERVER_BROWSER_FQDN = os.environ.get("SERVER_BROWSER_FQDN", "chivalry2-server-browser-backend")

_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
)

token_reissuer = TokenReissuer(
    private_key=_private_key,
    kid="server-browser-backend-key-1",
    eos_jwks=EOS_JWKS_URL,
    expected_audience=EOS_AUDIENCE,
    issuer=SERVER_BROWSER_FQDN
)


class Banned(Exception):
    pass

def get_ip() -> str:
    return str(request.remote_addr)

def is_whitelisted() -> bool:
    ip = get_ip()
    return verified_list.contains(ip)

def get_and_validate_ip() -> str:
    ip = get_ip()
    if ban_list.contains(ip):
        raise Banned()

    return ip

def get_key() -> str:
    key = request.headers.get(KEY_HEADER)
    if not key:
        raise SecretKeyMissing()

    return key

def get_json() -> Dict[str, Any]:
    if not request.is_json:
        raise JsonMissing()

    json = request.get_json(silent=True)
    if json is None:
        raise JsonMissing()

    return json
