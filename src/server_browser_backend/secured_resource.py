from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Callable, Generic, Optional

from server_browser_backend.type_vars import A


@dataclass(frozen=True)
class SecuredResource(Generic[A]):
    """A secured resource can be fetched with no secret key, but can only be updated with the proper secret_key."""

    secret_key: str
    resource: A

    def validate(self, secret_key: str) -> bool:
        return secrets.compare_digest(self.secret_key, secret_key)

    def with_resource(
        self, secret_key: str, new_resource: A
    ) -> Optional[SecuredResource[A]]:
        """Validates the secret key and updates the resource with the update_func."""
        if self.validate(secret_key):
            return SecuredResource(secret_key, new_resource)

        return None
