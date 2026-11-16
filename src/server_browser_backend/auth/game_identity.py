"""Verify public account-control proofs, never a joining player's credential.

Upstream contract: PlayFab/API_Specs@80e104aa, Client/GetUserData.
The independent verifier session is operator-provisioned, not client supplied.
"""

from __future__ import annotations

import http.client
import json
import hmac
import re
import urllib.error
import urllib.request
from dataclasses import dataclass


class InvalidGameCredential(Exception):
    """Rejected account-control proof; never includes secrets."""


class GameIdentityUnavailable(Exception):
    """Verification could not complete. Never treat this as authenticated."""


@dataclass(frozen=True)
class VerifiedGameIdentity:
    playfab_id: str
    linked_steam_id: str | None = None

    def __post_init__(self):
        if (
            not isinstance(self.playfab_id, str)
            or re.fullmatch(r"[0-9A-Fa-f]{1,64}", self.playfab_id) is None
        ):
            raise ValueError("Invalid PlayFab identity")
        object.__setattr__(self, "playfab_id", self.playfab_id.upper())
        steam = self.linked_steam_id
        if steam is not None and (
            not isinstance(steam, str)
            or re.fullmatch(r"[1-9][0-9]{0,19}", steam) is None
            or int(steam) >= 2**64
        ):
            raise ValueError("Invalid linked Steam identity")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


class PlayFabIdentityVerifier:
    """Fixed HTTPS public-data reader using the verifier's own bearer credential."""

    def __init__(
        self, session_ticket: str, title_id: str = "EBF8D", *, timeout: float = 5
    ):
        if (
            not isinstance(title_id, str)
            or re.fullmatch(r"[A-Za-z0-9]{1,16}", title_id) is None
        ):
            raise ValueError("Invalid PlayFab title ID")
        if not 0 < timeout <= 30:
            raise ValueError("Invalid verification timeout")
        if (
            not isinstance(session_ticket, str)
            or not 1 <= len(session_ticket) <= 8192
            or any(not 33 <= ord(char) <= 126 for char in session_ticket)
        ):
            raise ValueError("Invalid verifier session configuration")
        self._session_ticket = session_ticket
        self.url = f"https://{title_id}.playfabapi.com/Client/GetUserData"
        self.timeout = timeout
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect()
        )

    def _call(self, operation: str, body: dict) -> dict:
        # Operations are selected internally, never from a client-supplied URL.
        request = urllib.request.Request(
            self.url.rsplit("/", 1)[0] + "/" + operation,
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Authorization": self._session_ticket,
            },
        )
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise GameIdentityUnavailable(
                        "Game identity verification unavailable"
                    )
                body = response.read(65537)
            if len(body) > 65536:
                raise GameIdentityUnavailable("Game identity response exceeds limit")
        except urllib.error.HTTPError as error:
            # Do not retain upstream error bodies or credential-bearing exceptions.
            error.close()
            # These reject the verifier's login or title policy, not the claimant.
            raise GameIdentityUnavailable(
                "Game identity verification unavailable"
            ) from None
        except (OSError, TimeoutError, http.client.HTTPException):
            raise GameIdentityUnavailable(
                "Game identity verification unavailable"
            ) from None
        try:
            payload = json.loads(body)
            if type(payload.get("code")) is not int or payload["code"] != 200:
                raise ValueError()
            if type(payload.get("data")) is not dict:
                raise ValueError()
            return payload["data"]
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            raise GameIdentityUnavailable("Invalid game identity response") from None

    def verify(self, playfab_id: str, proof: str) -> VerifiedGameIdentity:
        identity = VerifiedGameIdentity(playfab_id)
        if (
            not isinstance(proof, str)
            or re.fullmatch(r"uc-proof-v1:[0-9a-f]{64}", proof) is None
        ):
            raise InvalidGameCredential("Invalid account-control proof")
        payload = self._call(
            "GetUserData", {"PlayFabId": identity.playfab_id, "Keys": ["UnchainedJoin_v1"]}
        )
        try:
            data = payload["Data"]
            if type(data) is not dict:
                raise ValueError()
            record = data.get("UnchainedJoin_v1")
            if record is None:
                raise InvalidGameCredential("Account-control proof missing")
            if type(record) is not dict or type(record.get("Value")) is not str:
                raise ValueError()
            if record.get("Permission") != "Public" or not hmac.compare_digest(
                record["Value"], proof
            ):
                raise InvalidGameCredential("Account-control proof rejected")
            return identity
        except InvalidGameCredential:
            raise
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            raise GameIdentityUnavailable("Invalid game identity response") from None

    def verify_steam_link(
        self, identity: VerifiedGameIdentity, steam_id: str
    ) -> VerifiedGameIdentity:
        """Read the title's Steam association using the verifier's own session.

        The caller must separately verify PlayFab control and the EOS proof that
        supplied this Steam ID; neither a client claim nor this lookup is login.
        """
        try:
            if steam_id is None:
                raise ValueError()
            linked = VerifiedGameIdentity(identity.playfab_id, steam_id)
        except (ValueError, TypeError, AttributeError):
            raise InvalidGameCredential("Invalid Steam identity") from None
        payload = self._call("GetPlayFabIDsFromSteamIDs", {"SteamStringIDs": [steam_id]})
        try:
            pairs = payload["Data"]
            if type(pairs) is not list:
                raise ValueError()
            if not pairs:
                raise InvalidGameCredential("Steam account is not linked")
            if len(pairs) != 1 or type(pairs[0]) is not dict:
                raise ValueError()
            pair = pairs[0]
            if pair.get("SteamStringId") != steam_id:
                raise ValueError()
            playfab = pair.get("PlayFabId")
            if playfab is None:
                raise InvalidGameCredential("Steam account is not linked")
            actual = VerifiedGameIdentity(playfab)
            if actual.playfab_id != identity.playfab_id:
                raise InvalidGameCredential("Steam and PlayFab accounts do not match")
            return linked
        except InvalidGameCredential:
            raise
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            raise GameIdentityUnavailable("Invalid Steam identity response") from None
