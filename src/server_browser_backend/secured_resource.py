from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Generic, Optional

from server_browser_backend.type_vars import A


@dataclass(frozen=True)
class SecuredResource(Generic[A]):
    """A secured resource can be fetched with no secret key, but can only be updated with the proper secret_key."""

    secret_key: str
    resource: A

    def __post_init__(self) -> None:
        if not self.secret_key or not self.secret_key.isascii():
            raise ValueError("Secret keys must be nonempty ASCII strings")

    def validate(self, secret_key: str) -> bool:
        return secret_key.isascii() and secrets.compare_digest(
            self.secret_key, secret_key
        )

    def with_resource(
        self, secret_key: str, new_resource: A
    ) -> Optional[SecuredResource[A]]:
        """Return a replacement resource when the secret key is valid."""
        if self.validate(secret_key):
            return SecuredResource(secret_key, new_resource)

        return None
