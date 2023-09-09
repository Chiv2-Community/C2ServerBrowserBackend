import os
import secrets

from flask import request

from server_browser_backend.ip_list import IpList
from server_browser_backend.server_list import SecretKeyMissing, ServerList

ADMIN_KEY = os.environ.get("ADMIN_KEY", secrets.token_urlsafe(128))
CONFIG_DIR = os.environ.get("CONFIG_DIR", "config")

DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"

ADMIN_KEY_HEADER = "x-chiv2-server-browser-admin-key"
KEY_HEADER = "x-chiv2-server-browser-key"

heartbeat_timeout = 65
server_list: ServerList = ServerList(heartbeat_timeout)

ban_list: IpList = IpList(ADMIN_KEY, f"{CONFIG_DIR}/ban_list.txt")
allow_list: IpList = IpList(ADMIN_KEY, f"{CONFIG_DIR}/allow_list.txt")


class Banned(Exception):
    pass

class NotWhitelisted(Exception):
    pass

def get_ip() -> str:
    return str(request.headers.get("X-Forwarded-For", request.remote_addr))

def is_whitelisted() -> bool:
    ip = get_ip()
    if ip in allow_list.get_all():
        return True
    return False

def get_and_validate_ip(registering: bool = False) -> str:
    ip = get_ip()
    if ip in ban_list.get_all():
        raise Banned()
    
    if registering:
        if not is_whitelisted():
            raise NotWhitelisted()

    return ip


def get_key() -> str:
    key = request.headers.get(KEY_HEADER)
    if not key:
        raise SecretKeyMissing()

    return key
