from __future__ import annotations

import logging
import secrets
import threading
from datetime import datetime
from typing import Callable, Dict, List, Optional

from server_browser_backend.models.base_models import Server
from server_browser_backend.secured_resource import SecuredResource

logger = logging.getLogger(__name__)


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

    def delete(self, server_id: str, key: str) -> Optional[Server]:
        """Remove the server with the given id from the server list and return it."""
        with self.servers_mutex:
            server = self.servers.get(server_id)
            if server is None:
                return None

            if not server.validate(key):
                raise InvalidSecretKey()
            del self.servers[server_id]
            return server.resource

    def get(self, server_id: str) -> Optional[Server]:
        """Gets the server with the given id."""
        with self.servers_mutex:
            secured_server = self.servers.get(server_id)
            if secured_server is None:
                return None

            return secured_server.resource

    def get_all(self) -> List[Server]:
        """Gets all registered servers that have not timed out."""
        with self.servers_mutex:
            current_time = datetime.now().timestamp()
            expired = self._process_heartbeat_timeouts(current_time)
            servers = [
                secured_server.resource for secured_server in self.servers.values()
            ]
        # Log outside the lock: a remote log sink must not block registry operations.
        for server in expired:
            logger.info(
                "Server registration expired server_id=%r name=%r ip=%s game_port=%s age_seconds=%.1f timeout_seconds=%s",
                server.unique_id,
                server.name,
                server.ip_address,
                server.ports.game,
                current_time - server.last_heartbeat,
                self.heartbeat_timeout,
            )
        return servers

    def clear(self) -> None:
        """Clears all registered servers."""
        with self.servers_mutex:
            self.servers.clear()

    def _process_heartbeat_timeouts(self, current_time: float) -> List[Server]:
        """Remove expired records while the caller holds the registry lock."""
        expired = [
            server_id
            for server_id, server in self.servers.items()
            if server.resource.last_heartbeat + self.heartbeat_timeout < current_time
        ]
        return [self.servers.pop(server_id).resource for server_id in expired]
