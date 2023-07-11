from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Generic, Optional
from server_browser_backend.type_vars import A


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