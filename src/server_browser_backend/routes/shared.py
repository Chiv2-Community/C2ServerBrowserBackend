"""Request policy shared by the API implementations."""
from fastapi import Request

from server_browser_backend.ip_list import IpList

ADMIN_KEY_HEADER = "x-chiv2-server-browser-admin-key"
KEY_HEADER = "x-chiv2-server-browser-key"


class Banned(Exception):
    pass


def get_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "None"


class RequestPolicy:
    def __init__(self, ban_list: IpList, verified_list: IpList):
        self.ban_list = ban_list
        self.verified_list = verified_list

    def is_whitelisted(self, request: Request) -> bool:
        return self.verified_list.contains(get_ip(request))

    def get_and_validate_ip(self, request: Request) -> str:
        ip = get_ip(request)
        if self.ban_list.contains(ip):
            raise Banned()
        return ip
