"""Persistent, rotating RSA keys for Discord join tickets.

Provisioning is explicit. Readers reload the atomically replaced keyring so
independent workers share the same signing identity without a restart.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import stat
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from uuid import UUID, uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from server_browser_models.models import JoinTicketClaims, Jwk, JwksResponse

from server_browser_backend.auth.identity import validate_discord_id

TICKET_SECONDS = 60
CLOCK_SKEW_SECONDS = 30
MAX_KEYS = 8
MAX_KEYRING_BYTES = 64 * 1024


def public_jwk(key: rsa.RSAPublicKey, kid: str) -> Jwk:
    numbers = key.public_numbers()

    def encode(value: int) -> str:
        return (
            base64.urlsafe_b64encode(
                value.to_bytes((value.bit_length() + 7) // 8, "big")
            )
            .decode()
            .rstrip("=")
        )

    return Jwk(
        kty="RSA",
        alg="RS256",
        use="sig",
        kid=kid,
        n=encode(numbers.n),
        e=encode(numbers.e),
    )


class SigningKeys:
    def __init__(self, path: Path):
        self.path = path
        self._lock = Lock()
        self._version: tuple[int, int, int, int] | None = None
        self._snapshot: tuple[rsa.RSAPrivateKey, str, list[dict]] | None = None
        self._load()  # Invalid configured keys must fail during startup.

    def _load(self) -> tuple[rsa.RSAPrivateKey, str, list[dict]]:
        # Only one bounded snapshot per worker. Public JWKS reads must not
        # repeatedly perform expensive RSA private-key validation.
        with self._lock:
            info = self.path.stat()
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("Signing keyring must be a regular file")
            version = (info.st_ino, info.st_mtime_ns, info.st_ctime_ns, info.st_size)
            if version != self._version or self._snapshot is None:
                self._snapshot = self._read()
                self._version = version
            return self._snapshot

    def _read(self) -> tuple[rsa.RSAPrivateKey, str, list[dict]]:
        with self.path.open("rb") as stream:
            permissions = os.fstat(stream.fileno())
            if os.name == "posix" and stat.S_IMODE(permissions.st_mode) & 0o077:
                raise ValueError(
                    "Signing keyring must not be accessible to group or other users"
                )
            data = stream.read(MAX_KEYRING_BYTES + 1)
        if len(data) > MAX_KEYRING_BYTES:
            raise ValueError("Signing keyring exceeds the size limit")
        try:
            document = json.loads(data)
            if set(document) != {"active_kid", "keys"}:
                raise ValueError
            entries = document["keys"]
            if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_KEYS:
                raise ValueError
            seen = set()
            active = None
            for entry in entries:
                kid = entry["kid"]
                if not isinstance(kid, str) or str(UUID(kid)) != kid or kid in seen:
                    raise ValueError
                seen.add(kid)
                if kid == document["active_kid"]:
                    if set(entry) != {"kid", "private_key"}:
                        raise ValueError
                    key = serialization.load_pem_private_key(
                        entry["private_key"].encode(), password=None
                    )
                    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
                        raise ValueError
                    active = key
                else:
                    if set(entry) != {"kid", "public_key", "retire_after"}:
                        raise ValueError
                    if (
                        type(entry["retire_after"]) is not int
                        or entry["retire_after"] < 0
                    ):
                        raise ValueError
                    public = serialization.load_pem_public_key(
                        entry["public_key"].encode()
                    )
                    if (
                        not isinstance(public, rsa.RSAPublicKey)
                        or public.key_size < 2048
                    ):
                        raise ValueError
            if active is None:
                raise ValueError
            return active, document["active_kid"], entries
        except (ValueError, TypeError, KeyError, AttributeError):
            # Never include serialized keys or parser details in diagnostics.
            raise ValueError("Invalid signing keyring") from None

    def get_jwks_response(self) -> JwksResponse:
        active, kid, entries = self._load()
        keys = [public_jwk(active.public_key(), kid)]
        for entry in entries:
            if entry["kid"] != kid and entry["retire_after"] > time.time():
                public = serialization.load_pem_public_key(entry["public_key"].encode())
                assert isinstance(public, rsa.RSAPublicKey)
                keys.append(public_jwk(public, entry["kid"]))
        return JwksResponse(keys=keys)

    def issue_join_ticket(
        self, *, issuer: str, discord_id: str, server_id: str, auth_time: int
    ) -> str:
        """Internal issuance boundary; callers must authenticate the session first."""
        from urllib.parse import urlsplit

        parsed = urlsplit(issuer)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Join issuer must be a fixed HTTPS URL")
        validate_discord_id(discord_id)
        if str(UUID(server_id)) != server_id:
            raise ValueError("Invalid server registration ID")
        now = int(time.time())
        if type(auth_time) is not int or not 0 < auth_time <= now:
            raise ValueError("Invalid authentication time")
        key, kid, _ = self._load()
        claims = JoinTicketClaims(
            iss=issuer,
            sub=discord_id,
            aud=f"urn:unchained:server:{server_id}",
            purpose="unchained.join",
            auth_time=auth_time,
            iat=now,
            nbf=now,
            exp=now + TICKET_SECONDS,
            jti=str(uuid4()),
        )
        return jwt.encode(
            claims.model_dump(by_alias=True),
            key,
            algorithm="RS256",
            headers={"kid": kid, "typ": "unchained-join+jwt"},
        )


@contextmanager
def provisioning_lock(path: Path):
    # Provisioning runs on the Linux backend host, not in an HTTP request.
    import fcntl

    descriptor = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def provision(path: Path, *, rotate: bool = False) -> None:
    """Create or rotate a keyring without dropping still-valid verification keys."""
    with provisioning_lock(path):
        entries = []
        if rotate:
            old, kid, previous = SigningKeys(path)._load()
            now = int(time.time())
            entries = [
                entry
                for entry in previous
                if entry["kid"] != kid and entry["retire_after"] > now
            ]
            entries.append(
                {
                    "kid": kid,
                    "public_key": old.public_key()
                    .public_bytes(
                        serialization.Encoding.PEM,
                        serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                    .decode(),
                    "retire_after": now + TICKET_SECONDS + CLOCK_SKEW_SECONDS,
                }
            )
        elif path.exists():
            raise FileExistsError("Signing keyring already exists")
        if len(entries) >= MAX_KEYS:
            raise ValueError(
                "Rotation capacity reached; wait for retained keys to expire"
            )
        kid = str(uuid4())
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        entries.append(
            {
                "kid": kid,
                "private_key": private.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ).decode(),
            }
        )
        document = {"active_kid": kid, "keys": entries}
        descriptor, temporary = tempfile.mkstemp(prefix=".signing-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w") as output:
                json.dump(document, output)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            Path(temporary).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provision persistent Discord join-signing keys (Linux host)."
    )
    parser.add_argument("action", choices=["init", "rotate"])
    parser.add_argument("path", type=Path)
    arguments = parser.parse_args()
    provision(arguments.path, rotate=arguments.action == "rotate")


if __name__ == "__main__":
    main()
