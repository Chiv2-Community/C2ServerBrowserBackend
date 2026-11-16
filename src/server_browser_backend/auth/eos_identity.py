"""Verify identity-only EOS Connect JWTs, never access tokens or EOS Auth IDs.

Contract: https://dev.epicgames.com/docs/game-services/connect/connect-reference
All trust settings are operator-pinned; JWT headers cannot select a key URL.
"""

from __future__ import annotations

import http.client
import json
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit

import jwt

from server_browser_backend.auth.game_identity import (
    GameIdentityUnavailable,
    InvalidGameCredential,
    _NoRedirect,
)

JWKS_URL = "https://api.epicgames.dev/auth/v1/oauth/jwks"


@dataclass(frozen=True)
class VerifiedEosIdentity:
    product_user_id: str
    platform_provider: str
    platform_id: str
    expires_at: int


class EosConnectVerifier:
    def __init__(
        self,
        *,
        issuer: str,
        client_id: str,
        product_id: str,
        sandbox_id: str,
        deployment_id: str,
        timeout: float = 5,
    ):
        parsed = urlsplit(issuer)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "api.epicgames.dev"
            or parsed.query
            or parsed.fragment
            or not all(
                isinstance(value, str)
                and 1 <= len(value) <= 256
                and all(33 <= ord(char) <= 126 for char in value)
                for value in (issuer, client_id, product_id, sandbox_id, deployment_id)
            )
            or not 0 < timeout <= 30
        ):
            raise ValueError("Invalid pinned EOS Connect trust configuration")
        self.issuer = issuer
        self.client_id = client_id
        self.bindings = {
            "pfpid": product_id,
            "pfsid": sandbox_id,
            "pfdid": deployment_id,
        }
        self.timeout = timeout
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect()
        )
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: float | None = None
        self._lock = threading.Lock()

    def _key(self, kid: str) -> jwt.PyJWK:
        with self._lock:
            now = time.monotonic()
            age = float("inf") if self._fetched_at is None else now - self._fetched_at
            if age >= 300 or (kid not in self._keys and age >= 5):
                try:
                    with self._opener.open(JWKS_URL, timeout=self.timeout) as response:
                        if response.status != 200:
                            raise ValueError()
                        body = response.read(65537)
                    if len(body) > 65536:
                        raise ValueError()
                    document = json.loads(body)
                    entries = document["keys"]
                    if not isinstance(entries, list) or not 1 <= len(entries) <= 8:
                        raise ValueError()
                    keys = {}
                    for entry in entries:
                        key_id = entry["kid"]
                        if (
                            not isinstance(key_id, str)
                            or not 1 <= len(key_id) <= 128
                            or key_id in keys
                            or entry.get("kty") != "RSA"
                            or entry.get("alg", "RS256") != "RS256"
                            or entry.get("use", "sig") != "sig"
                            or any(name in entry for name in ("d", "p", "q"))
                        ):
                            raise ValueError()
                        key = jwt.PyJWK.from_dict(entry, algorithm="RS256")
                        if not 2048 <= key.key.key_size <= 8192:
                            raise ValueError()
                        keys[key_id] = key
                    self._keys = keys
                    self._fetched_at = time.monotonic()
                except urllib.error.HTTPError as error:
                    error.close()
                    raise GameIdentityUnavailable(
                        "EOS verification keys unavailable"
                    ) from None
                except (
                    OSError,
                    TimeoutError,
                    http.client.HTTPException,
                    ValueError,
                    TypeError,
                    KeyError,
                    AttributeError,
                    RecursionError,
                    jwt.PyJWTError,
                ):
                    raise GameIdentityUnavailable(
                        "EOS verification keys unavailable"
                    ) from None
            selected = self._keys.get(kid)
            if selected is None:
                raise InvalidGameCredential("Unknown EOS verification key")
            return selected

    def verify(self, token: str) -> VerifiedEosIdentity:
        if not isinstance(token, str) or not 1 <= len(token) <= 16384:
            raise InvalidGameCredential("Invalid EOS identity proof")
        try:
            header = jwt.get_unverified_header(token)
            kid = header["kid"]
            if (
                header.get("alg") != "RS256"
                or not isinstance(kid, str)
                or not 1 <= len(kid) <= 128
                or any(name in header for name in ("jku", "jwk", "x5u", "crit", "b64"))
            ):
                raise ValueError()
            key = self._key(kid)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.client_id,
                leeway=5,
                options={
                    "require": [
                        "iss",
                        "aud",
                        "sub",
                        "iat",
                        "exp",
                        "pfpid",
                        "pfsid",
                        "pfdid",
                        "act",
                    ],
                    "strict_aud": True,
                },
            )
            if (
                any(
                    claims.get(name) != expected
                    for name, expected in self.bindings.items()
                )
                or type(claims["iat"]) is not int
                or type(claims["exp"]) is not int
                or claims["exp"] <= max(int(time.time()), claims["iat"])
                or not isinstance(claims["sub"], str)
                or re.fullmatch(r"[0-9a-f]{32}", claims["sub"]) is None
                or type(claims["act"]) is not dict
            ):
                raise ValueError()
            account = claims["act"]
            if account.get("eat") == "steam":
                steam = account.get("eaid")
                if (
                    not isinstance(steam, str)
                    or re.fullmatch(r"[0-9]{1,20}", steam) is None
                    or not 0 < int(steam) < 2**64
                ):
                    raise ValueError()
                provider, platform = "steam", str(int(steam))
            elif account.get("eat") == "epicgames":
                if (
                    not isinstance(account.get("eaid"), str)
                    or re.fullmatch(r"[0-9a-fA-F]{32}", account["eaid"]) is None
                ):
                    raise ValueError()
                provider, platform = "eos", claims["sub"]
            else:
                raise ValueError()
            return VerifiedEosIdentity(claims["sub"], provider, platform, claims["exp"])
        except (
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            RecursionError,
            jwt.PyJWTError,
        ):
            raise InvalidGameCredential("EOS identity proof rejected") from None
