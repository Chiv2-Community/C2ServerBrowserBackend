from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Generic, List, Optional, TypeVar

from server_browser_backend.models import Server
from server_browser_backend.type_vars import A


class InvalidSecretKey(Exception):
    pass


class SecretKeyMissing(Exception):
    pass


@dataclass(frozen=True)
class SecuredResource(Generic[A]):
    """A secured resource can be fetched with no secret key, but can only be updated with the proper secret_key."""

    secret_key: str
    resource: A

    def validate(self, secret_key: str) -> bool:
        return self.secret_key == secret_key

    def update(
        self, secret_key: str, update_func: Callable[[A], A]
    ) -> Optional[SecuredResource[A]]:
        """Validates the secret key and updates the resource with the update_func."""
        if self.validate(secret_key):
            update_result = update_func(self.resource)
            return SecuredResource(secret_key, update_result)

        return None


class ServerList:
    """Maintains a map of servers keyed off their unique id.
    Servers are registered with a unique id and a secret key.
    Servers can update their information with the secret key.
    """

    def __init__(self, heartbeat_timeout: float = 65):
        self.servers: Dict[str, SecuredResource[Server]] = {}
        self.heartbeat_timeout = heartbeat_timeout

    def exists(self, server_id: str) -> bool:
        """Returns true if a server with the given id exists."""
        return server_id in self.servers

    def register(self, server: Server) -> str:
        """Registers a server and returns a secret key."""
        key = secrets.token_hex(128)
        secured_resource = SecuredResource(key, server)
        self.servers[server.unique_id] = secured_resource
        return key

    def update(
        self, server_id: str, key: str, func: Callable[[Server], Server]
    ) -> Server:
        """Updates a server with the given id and key."""
        secured_server = self.servers[server_id]
        result = secured_server.update(key, func)

        if result is None:
            raise InvalidSecretKey()

        self.servers[server_id] = result

        return result.resource

    def get(self, server_id: str) -> Optional[Server]:
        """Gets the server with the given id."""
        secured_server = self.servers.get(server_id)
        if secured_server is None:
            return None

        return secured_server.resource

    def get_unsafe(self, server_id: str) -> Server:
        """Gets the server with the given id. Raises an exception if the server does not exist."""
        return self.servers[server_id].resource

    def get_all(self) -> List[Server]:
        """Gets all registered servers that have not timed out."""
        self._process_heartbeat_timeouts(datetime.now().timestamp())
        return [secured_server.resource for secured_server in self.servers.values()]

    def clear(self) -> None:
        """Clears all registered servers."""
        self.servers.clear()

    def _process_heartbeat_timeouts(self, current_time: float) -> None:
        """Removes any servers that have timed out."""
        delete_keys = []
        for server_id, secured_server in self.servers.items():
            if (
                secured_server.resource.last_heartbeat + self.heartbeat_timeout
                < current_time
            ):
                delete_keys.append(server_id)

        for server_id in delete_keys:
            del self.servers[server_id]
