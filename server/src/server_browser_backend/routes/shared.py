from typing import List

from flask import request

from server_browser_backend.server_list import SecretKeyMissing, ServerList

ADMIN_KEY_HEADER = "x-chiv2-server-browser-admin-key"

KEY_HEADER = "x-chiv2-server-browser-key"

ban_list: List[str] = []

heartbeat_timeout = 65
server_list: ServerList = ServerList(heartbeat_timeout)


class Banned(Exception):
    pass


def get_ip() -> str:
    return str(request.headers.get("X-Forwarded-For", request.remote_addr))


def get_and_validate_ip() -> str:
    ip = get_ip()
    if ip in ban_list:
        raise Banned()

    return ip


def get_key() -> str:
    key = request.headers.get(KEY_HEADER)
    if not key:
        raise SecretKeyMissing()

    return key
