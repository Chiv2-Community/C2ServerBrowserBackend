"""Framework-neutral request policy and responses shared by the API implementations."""
from server_browser_models.models import StatusResponse
from server_browser_server.runtime import ApiResponse, RequestContext

from server_browser_backend.ip_list import IpList

ADMIN_KEY_HEADER = "x-chiv2-server-browser-admin-key"
KEY_HEADER = "x-chiv2-server-browser-key"


def status(code: str, message: str, http_status: int) -> ApiResponse[StatusResponse]:
    return ApiResponse(StatusResponse(status=code, message=message), http_status)


class Banned(Exception):
    pass


def get_ip(request: RequestContext) -> str:
    return request.client_ip


class RequestPolicy:
    def __init__(self, ban_list: IpList, verified_list: IpList):
        self.ban_list = ban_list
        self.verified_list = verified_list

    def is_whitelisted(self, request: RequestContext) -> bool:
        return self.verified_list.contains(get_ip(request))

    def get_and_validate_ip(self, request: RequestContext) -> str:
        ip = get_ip(request)
        if self.ban_list.contains(ip):
            raise Banned()
        return ip
