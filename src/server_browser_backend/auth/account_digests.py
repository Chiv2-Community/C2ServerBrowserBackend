"""Deterministic, namespaced HMACs. Key provisioning is explicit, never per boot."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import stat
from dataclasses import dataclass, field
from pathlib import Path

FORMAT = "hmac-sha256-v1"


@dataclass(frozen=True)
class AccountDigester:
    key: bytes = field(repr=False)

    def __post_init__(self):
        if type(self.key) is not bytes or len(self.key) != 32:
            raise ValueError("Account HMAC key must contain exactly 32 bytes")

    @classmethod
    def load(cls, path: Path) -> AccountDigester:
        # Refuse symlinks and inspect the actual descriptor, not just its pathname.
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Account HMAC key must be a private regular file")
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        with os.fdopen(descriptor, "rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or (
                os.name == "posix" and stat.S_IMODE(info.st_mode) & 0o077
            ):
                raise ValueError("Account HMAC key must be a private regular file")
            return cls(source.read(33))

    def digest(self, provider: str, canonical_id: str) -> bytes:
        if provider not in {"playfab", "steam", "eos"}:
            raise ValueError("Unsupported account digest namespace")
        return hmac.digest(
            self.key,
            b"unchained-account-id-v1\0"
            + provider.encode("ascii")
            + b"\0"
            + canonical_id.encode("ascii"),
            hashlib.sha256,
        )

    @property
    def key_check(self) -> bytes:
        # A domain-separated check detects accidental key replacement, even for
        # empty databases. It is not the secret key or a hash of any player ID.
        return hmac.digest(self.key, b"unchained-account-key-check-v1", hashlib.sha256)


def provision_key(path: Path) -> None:
    """Create once; never overwrite an existing key or print its contents."""
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(secrets.token_bytes(32))
        output.flush()
        os.fsync(output.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
