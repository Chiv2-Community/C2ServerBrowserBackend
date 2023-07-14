from __future__ import annotations

import secrets
from datetime import datetime
import threading
from typing import Callable, Dict, List, Optional

from server_browser_backend.models.base_models import Server
from server_browser_backend.secured_resource import SecuredResource


class InvalidSecretKey(Exception):
    pass


class SecretKeyMissing(Exception):
    pass


class ServerList:
    """Maintains a map of servers keyed off their unique id.
    Servers are registered with a unique id and a secret key.
    Servers can update their information with the secret key.
    """

    def __init__(self, heartbeat_timeout: float = 65):
        self.servers: Dict[str, SecuredResource[Server]] = {}
        self.heartbeat_timeout = heartbeat_timeout
        self.servers_mutex = threading.Lock()

    def exists(self, server_id: str) -> bool:
        """Returns true if a server with the given id exists."""
        with self.servers_mutex:
            return server_id in self.servers

    def register(self, server: Server) -> str:
        """Registers a server and returns a secret key."""
        with self.servers_mutex:
            key = secrets.token_hex(128)
            secured_resource = SecuredResource(key, server)
            self.servers[server.unique_id] = secured_resource
            return key

    def update(
        self, server_id: str, key: str, func: Callable[[Server], Server]
    ) -> Optional[Server]:
        """Updates a server with the given id and key."""
        with self.servers_mutex:
            secured_server = self.servers.get(server_id)
            if secured_server is None:
                return None
            result = secured_server.with_resource(key, func(secured_server.resource))

            if result is None:
                raise InvalidSecretKey()

            self.servers[server_id] = result

            return result.resource
    
    def delete(
        self, server_id: str, key: str
    ) -> Optional[Server]:
        """Remove the server with the given id from the server list and return it."""
        with self.servers_mutex:
            server = self.servers.get(server_id)
            if server is None:
                return None
            
            if server.validate(key):
                serverResource = server.resource
                del self.servers[server_id]
                return serverResource
            else:
                raise InvalidSecretKey()

    def get(self, server_id: str) -> Optional[Server]:
        """Gets the server with the given id."""
        with self.servers_mutex:
            secured_server = self.servers.get(server_id)
            if secured_server is None:
                return None

            return secured_server.resource

    def get_unsafe(self, server_id: str) -> Server:
        """Gets the server with the given id. Raises an exception if the server does not exist."""
        with self.servers_mutex:
            return self.servers[server_id].resource

    def get_all(self) -> List[Server]:
        """Gets all registered servers that have not timed out."""
        with self.servers_mutex:
            self._process_heartbeat_timeouts(datetime.now().timestamp())
            return [secured_server.resource for secured_server in self.servers.values()]

    def clear(self) -> None:
        """Clears all registered servers."""
        with self.servers_mutex:
            self.servers.clear()

    def _process_heartbeat_timeouts(self, current_time: float) -> None:
        """Removes any servers that have timed out. No mutex here because its always called from within a mutex lock."""
        delete_keys = []
        for server_id, secured_server in self.servers.items():
            if (
                secured_server.resource.last_heartbeat + self.heartbeat_timeout
                < current_time
            ):
                delete_keys.append(server_id)

        for server_id in delete_keys:
            del self.servers[server_id]
