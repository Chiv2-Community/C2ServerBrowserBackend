"""Framework-neutral request policy and responses shared by the API implementations."""
from server_browser_models.models import StatusResponse
from server_browser_server.runtime import ApiResponse, RequestContext

from server_browser_backend.ip_list import IpList
from server_browser_backend.ip_address import canonical_address
from server_browser_backend.models.base_models import Server

ADMIN_KEY_HEADER = "x-chiv2-server-browser-admin-key"
KEY_HEADER = "x-chiv2-server-browser-key"


def status(code: str, message: str, http_status: int) -> ApiResponse[StatusResponse]:
    return ApiResponse(StatusResponse(status=code, message=message), http_status)


class Banned(Exception):
    pass


def get_ip(request: RequestContext) -> str:
    try:
        return str(canonical_address(request.client_ip))
    except ValueError:
        return request.client_ip


class RequestPolicy:
    def __init__(self, ban_list: IpList, verified_list: IpList):
        self.ban_list = ban_list
        self.verified_list = verified_list

    def with_current_verification(self, server: Server) -> Server:
        if self.verified_list.contains(str(server.ip_address)):
            return server.verified()
        return server.unverified()

    def get_and_validate_ip(self, request: RequestContext) -> str:
        ip = get_ip(request)
        if self.ban_list.contains(ip):
            raise Banned()
        return ip
