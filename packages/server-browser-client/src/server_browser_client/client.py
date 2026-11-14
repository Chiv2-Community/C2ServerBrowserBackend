"""Generated typed HTTP clients. DO NOT EDIT."""
from __future__ import annotations
from typing import Any, Dict, List
from server_browser_models.models import *
from server_browser_models.runtime import IPAddress, LegacyIPAddress
from server_browser_client.runtime import (
    AsyncClientTransport, ClientTransport, ClientResponse, UNSET, Unset,
)


class Client(ClientTransport):

    def jwks(self) -> ClientResponse[JwksResponse | StatusResponse]:
        return self._request("jwks", parameters={ })

    def login(self, *, login_request: LoginRequest) -> ClientResponse[StatusResponse | StatusResponse]:
        return self._request("login", parameters={ }, body=login_request)

    def send_swagger(self) -> ClientResponse[str | StatusResponse]:
        return self._request("send_swagger", parameters={ })

    def get_servers(self) -> ClientResponse[ServerListResponse | StatusResponse]:
        return self._request("get_servers", parameters={ })

    def register(self, *, server_registration_request: ServerRegistrationRequest) -> ClientResponse[StatusResponse | StatusResponse | RegistrationResponse | StatusResponse]:
        return self._request("register", parameters={ }, body=server_registration_request)

    def update(self, *, x_chiv2_server_browser_key: str | Unset = UNSET, server_id: str, update_registered_server: UpdateRegisteredServer) -> ClientResponse[StatusResponse | StatusResponse | StatusResponse | StatusResponse | UpdateResponse | StatusResponse]:
        return self._request("update", parameters={ "X-CHIV2-SERVER-BROWSER-KEY": x_chiv2_server_browser_key, "server_id": server_id, }, body=update_registered_server)

    def delete_server(self, *, x_chiv2_server_browser_key: str | Unset = UNSET, server_id: str) -> ClientResponse[StatusResponse | StatusResponse | StatusResponse | StatusResponse | StatusResponse]:
        return self._request("delete_server", parameters={ "X-CHIV2-SERVER-BROWSER-KEY": x_chiv2_server_browser_key, "server_id": server_id, })

    def heartbeat(self, *, x_chiv2_server_browser_key: str | Unset = UNSET, server_id: str) -> ClientResponse[StatusResponse | StatusResponse | StatusResponse | StatusResponse | UpdateResponse | StatusResponse]:
        return self._request("heartbeat", parameters={ "X-CHIV2-SERVER-BROWSER-KEY": x_chiv2_server_browser_key, "server_id": server_id, })

    def check_banned(self, *, ip: IPAddress) -> ClientResponse[BanStatusResponse | StatusResponse]:
        return self._request("check_banned", parameters={ "ip": ip, })

    def get_ban_list(self, *, x_chiv2_server_browser_admin_key: str | Unset = UNSET) -> ClientResponse[StatusResponse | BanListResponse | StatusResponse]:
        return self._request("get_ban_list", parameters={ "X-CHIV2-SERVER-BROWSER-ADMIN-KEY": x_chiv2_server_browser_admin_key, })

    def add_to_ban_list(self, *, x_chiv2_server_browser_admin_key: str | Unset = UNSET, ip_list_request: IpListRequest) -> ClientResponse[StatusResponse | StatusResponse | BanListResponse | StatusResponse]:
        return self._request("add_to_ban_list", parameters={ "X-CHIV2-SERVER-BROWSER-ADMIN-KEY": x_chiv2_server_browser_admin_key, }, body=ip_list_request)

    def remove_from_ban_list(self, *, x_chiv2_server_browser_admin_key: str | Unset = UNSET, ip_list_request: IpListRequest) -> ClientResponse[StatusResponse | StatusResponse | BanListResponse | StatusResponse]:
        return self._request("remove_from_ban_list", parameters={ "X-CHIV2-SERVER-BROWSER-ADMIN-KEY": x_chiv2_server_browser_admin_key, }, body=ip_list_request)

    def get_verified_list(self, *, x_chiv2_server_browser_admin_key: str | Unset = UNSET) -> ClientResponse[StatusResponse | VerifiedListResponse | StatusResponse]:
        return self._request("get_verified_list", parameters={ "X-CHIV2-SERVER-BROWSER-ADMIN-KEY": x_chiv2_server_browser_admin_key, })

    def add_to_verified_list(self, *, x_chiv2_server_browser_admin_key: str | Unset = UNSET, ip_list_request: IpListRequest) -> ClientResponse[StatusResponse | StatusResponse | VerifiedListResponse | StatusResponse]:
        return self._request("add_to_verified_list", parameters={ "X-CHIV2-SERVER-BROWSER-ADMIN-KEY": x_chiv2_server_browser_admin_key, }, body=ip_list_request)

    def remove_from_verified_list(self, *, x_chiv2_server_browser_admin_key: str | Unset = UNSET, ip_list_request: IpListRequest) -> ClientResponse[StatusResponse | StatusResponse | VerifiedListResponse | StatusResponse]:
        return self._request("remove_from_verified_list", parameters={ "X-CHIV2-SERVER-BROWSER-ADMIN-KEY": x_chiv2_server_browser_admin_key, }, body=ip_list_request)

    def tbio_get_servers(self) -> ClientResponse[TbioServerListResponse | StatusResponse]:
        return self._request("tbio_get_servers", parameters={ })

    def get_motd(self, *, motd_request: MotdRequest) -> ClientResponse[TbioMotdResponse | StatusResponse]:
        return self._request("get_motd", parameters={ }, body=motd_request)

    def playfab_client_matchmake(self, *, matchmake_request: MatchmakeRequest) -> ClientResponse[StatusResponse | PlayfabErrorResponse | PlayfabMatchmakeResponse | StatusResponse]:
        return self._request("playfab_client_matchmake", parameters={ }, body=matchmake_request)



class AsyncClient(AsyncClientTransport):

    async def jwks(self) -> ClientResponse[JwksResponse | StatusResponse]:
        return await self._request("jwks", parameters={ })

    async def login(self, *, login_request: LoginRequest) -> ClientResponse[StatusResponse | StatusResponse]:
        return await self._request("login", parameters={ }, body=login_request)

    async def send_swagger(self) -> ClientResponse[str | StatusResponse]:
        return await self._request("send_swagger", parameters={ })

    async def get_servers(self) -> ClientResponse[ServerListResponse | StatusResponse]:
        return await self._request("get_servers", parameters={ })

    async def register(self, *, server_registration_request: ServerRegistrationRequest) -> ClientResponse[StatusResponse | StatusResponse | RegistrationResponse | StatusResponse]:
        return await self._request("register", parameters={ }, body=server_registration_request)

    async def update(self, *, x_chiv2_server_browser_key: str | Unset = UNSET, server_id: str, update_registered_server: UpdateRegisteredServer) -> ClientResponse[StatusResponse | StatusResponse | StatusResponse | StatusResponse | UpdateResponse | StatusResponse]:
        return await self._request("update", parameters={ "X-CHIV2-SERVER-BROWSER-KEY": x_chiv2_server_browser_key, "server_id": server_id, }, body=update_registered_server)

    async def delete_server(self, *, x_chiv2_server_browser_key: str | Unset = UNSET, server_id: str) -> ClientResponse[StatusResponse | StatusResponse | StatusResponse | StatusResponse | StatusResponse]:
        return await self._request("delete_server", parameters={ "X-CHIV2-SERVER-BROWSER-KEY": x_chiv2_server_browser_key, "server_id": server_id, })

    async def heartbeat(self, *, x_chiv2_server_browser_key: str | Unset = UNSET, server_id: str) -> ClientResponse[StatusResponse | StatusResponse | StatusResponse | StatusResponse | UpdateResponse | StatusResponse]:
        return await self._request("heartbeat", parameters={ "X-CHIV2-SERVER-BROWSER-KEY": x_chiv2_server_browser_key, "server_id": server_id, })

    async def check_banned(self, *, ip: IPAddress) -> ClientResponse[BanStatusResponse | StatusResponse]:
        return await self._request("check_banned", parameters={ "ip": ip, })

    async def get_ban_list(self, *, x_chiv2_server_browser_admin_key: str | Unset = UNSET) -> ClientResponse[StatusResponse | BanListResponse | StatusResponse]:
        return await self._request("get_ban_list", parameters={ "X-CHIV2-SERVER-BROWSER-ADMIN-KEY": x_chiv2_server_browser_admin_key, })

    async def add_to_ban_list(self, *, x_chiv2_server_browser_admin_key: str | Unset = UNSET, ip_list_request: IpListRequest) -> ClientResponse[StatusResponse | StatusResponse | BanListResponse | StatusResponse]:
        return await self._request("add_to_ban_list", parameters={ "X-CHIV2-SERVER-BROWSER-ADMIN-KEY": x_chiv2_server_browser_admin_key, }, body=ip_list_request)

    async def remove_from_ban_list(self, *, x_chiv2_server_browser_admin_key: str | Unset = UNSET, ip_list_request: IpListRequest) -> ClientResponse[StatusResponse | StatusResponse | BanListResponse | StatusResponse]:
        return await self._request("remove_from_ban_list", parameters={ "X-CHIV2-SERVER-BROWSER-ADMIN-KEY": x_chiv2_server_browser_admin_key, }, body=ip_list_request)

    async def get_verified_list(self, *, x_chiv2_server_browser_admin_key: str | Unset = UNSET) -> ClientResponse[StatusResponse | VerifiedListResponse | StatusResponse]:
        return await self._request("get_verified_list", parameters={ "X-CHIV2-SERVER-BROWSER-ADMIN-KEY": x_chiv2_server_browser_admin_key, })

    async def add_to_verified_list(self, *, x_chiv2_server_browser_admin_key: str | Unset = UNSET, ip_list_request: IpListRequest) -> ClientResponse[StatusResponse | StatusResponse | VerifiedListResponse | StatusResponse]:
        return await self._request("add_to_verified_list", parameters={ "X-CHIV2-SERVER-BROWSER-ADMIN-KEY": x_chiv2_server_browser_admin_key, }, body=ip_list_request)

    async def remove_from_verified_list(self, *, x_chiv2_server_browser_admin_key: str | Unset = UNSET, ip_list_request: IpListRequest) -> ClientResponse[StatusResponse | StatusResponse | VerifiedListResponse | StatusResponse]:
        return await self._request("remove_from_verified_list", parameters={ "X-CHIV2-SERVER-BROWSER-ADMIN-KEY": x_chiv2_server_browser_admin_key, }, body=ip_list_request)

    async def tbio_get_servers(self) -> ClientResponse[TbioServerListResponse | StatusResponse]:
        return await self._request("tbio_get_servers", parameters={ })

    async def get_motd(self, *, motd_request: MotdRequest) -> ClientResponse[TbioMotdResponse | StatusResponse]:
        return await self._request("get_motd", parameters={ }, body=motd_request)

    async def playfab_client_matchmake(self, *, matchmake_request: MatchmakeRequest) -> ClientResponse[StatusResponse | PlayfabErrorResponse | PlayfabMatchmakeResponse | StatusResponse]:
        return await self._request("playfab_client_matchmake", parameters={ }, body=matchmake_request)
