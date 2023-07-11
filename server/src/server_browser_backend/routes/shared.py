import os
import secrets

from flask import request

from server_browser_backend.ban_list import BanList
from server_browser_backend.server_list import SecretKeyMissing, ServerList

ADMIN_KEY_HEADER = "x-chiv2-server-browser-admin-key"
ADMIN_KEY = os.environ.get("ADMIN_KEY", secrets.token_urlsafe(128))

KEY_HEADER = "x-chiv2-server-browser-key"


heartbeat_timeout = 65
server_list: ServerList = ServerList(heartbeat_timeout)

ban_list: BanList = BanList(ADMIN_KEY, "ban_list.txt")


class Banned(Exception):
    pass


def get_ip() -> str:
    return str(request.headers.get("X-Forwarded-For", request.remote_addr))


def get_and_validate_ip() -> str:
    ip = get_ip()
    if ip in ban_list.get():
        raise Banned()

    return ip


def get_key() -> str:
    key = request.headers.get(KEY_HEADER)
    if not key:
        raise SecretKeyMissing()

    return key
