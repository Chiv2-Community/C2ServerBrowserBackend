"""Opt-in game identity admission, coordinated with the live registry."""

from __future__ import annotations

import threading
import time
import hashlib
import hmac
import re
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from ipaddress import ip_address, IPv4Address, IPv6Address
from typing import Callable, Iterator, TypeVar

from server_browser_backend.auth.game_identity import (
    PlayFabIdentityVerifier,
    VerifiedGameIdentity,
)
from server_browser_backend.auth.game_join_tickets import (
    GameJoinTicketStore,
    GameJoinTicket,
)
from server_browser_backend.ip_address import canonical_address
from server_browser_backend.server_list import ServerList
from server_browser_backend.server_list import InvalidJoinRegistration
from server_browser_backend.auth.game_identity import InvalidGameCredential
from server_browser_backend.auth.game_join_tickets import GameJoinCapacity
from server_browser_backend.auth.game_identity import GameIdentityUnavailable
from server_browser_backend.auth.eos_identity import EosConnectVerifier, VerifiedEosIdentity
from server_browser_backend.auth.signing import SigningKeys

Proof = TypeVar("Proof")
Issued = TypeVar("Issued")


def account_proof(
    audience: str, server_id: str, playfab_id: str, challenge_id: str, commitment: str
) -> str:
    material = "\0".join(
        (
            "unchained-playfab-proof-v1",
            audience,
            server_id,
            playfab_id,
            challenge_id,
            commitment,
        )
    )
    return "uc-proof-v1:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GameJoinChallenge:
    challenge_id: str
    server_id: str
    generation: bytes
    source: str
    target_ip: IPv4Address | IPv6Address
    target_port: int
    playfab_id: str
    commitment: str
    proof: str
    expires_at: int


class GameJoinRateLimited(Exception):
    pass


class GameJoinService:
    def __init__(
        self,
        registry: ServerList,
        verifier: PlayFabIdentityVerifier,
        tickets: GameJoinTicketStore | None,
        audience: str,
        *,
        eos: EosConnectVerifier | None = None,
        signing: SigningKeys | None = None,
    ):
        self.registry = registry
        self.verifier = verifier
        self.tickets = tickets
        self.eos = eos
        self.signing = signing
        if not audience or len(audience) > 2048 or "\0" in audience:
            raise ValueError("Invalid game join audience")
        self.audience = audience
        self.clock = time.time
        # Like the registry, pending challenges are process-local. Restart loses
        # them safely; SQLite grants remain single-use across process restarts.
        self._challenges: dict[str, GameJoinChallenge] = {}
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(8)
        self._window = -1
        self._requests: dict[str, int] = {}
        self._total = 0

    @contextmanager
    def _admit(self, source: str, operation: str) -> Iterator[None]:
        # One bounded process-local limiter, matching the process-local registry.
        # Both accepted and rejected proof attempts consume the verification budget.
        with self._lock:
            window = int(time.monotonic() // 60)
            if self._window != window:
                self._window = window
                self._requests.clear()
                self._total = 0
            key = f"{operation}:{source}"
            count = self._requests.get(key, 0)
            if (
                self._total >= 1024
                or count >= (120 if operation == "redeem" else 12)
                or not self._slots.acquire(blocking=False)
            ):
                raise GameJoinRateLimited()
            self._requests[key] = count + 1
            self._total += 1
        try:
            yield
        finally:
            self._slots.release()

    def begin(
        self,
        source: str,
        target_ip: IPv4Address | IPv6Address,
        target_port: int,
        playfab_id: str,
        commitment: str,
        audience: str,
    ) -> GameJoinChallenge:
        source_ip = canonical_address(ip_address(source))
        target_ip = canonical_address(target_ip)
        identity = VerifiedGameIdentity(playfab_id)
        if (
            audience != self.audience
            or re.fullmatch(r"[0-9a-f]{64}", commitment) is None
        ):
            raise InvalidGameCredential("Invalid account-control challenge")
        with self._admit(str(source_ip), "begin"):
            with self.registry.join_target(source_ip, target_ip, target_port) as (
                server_id,
                generation,
            ):
                challenge_id = secrets.token_urlsafe(32)
                now = int(self.clock())
                challenge = GameJoinChallenge(
                    challenge_id,
                    server_id,
                    generation,
                    str(source_ip),
                    target_ip,
                    target_port,
                    identity.playfab_id,
                    commitment,
                    account_proof(
                        audience,
                        server_id,
                        identity.playfab_id,
                        challenge_id,
                        commitment,
                    ),
                    now + 60,
                )
                with self._lock:
                    self._challenges = {
                        key: value
                        for key, value in self._challenges.items()
                        if value.expires_at > now
                    }
                    # A claimed account is unauthenticated here. Do not let an
                    # attacker reserve a victim's per-account admission budget.
                    if (
                        len(self._challenges) >= 1024
                        or sum(
                            value.source == str(source_ip)
                            for value in self._challenges.values()
                        )
                        >= 12
                    ):
                        raise GameJoinCapacity("Game join challenge budget exhausted")
                    self._challenges[challenge_id] = challenge
                return challenge

    def issue(
        self, source: str, challenge_id: str, secret: str
    ) -> tuple[str, GameJoinTicket]:
        tickets = self.tickets
        if tickets is None:
            raise GameIdentityUnavailable("Opaque game join tickets are disabled")
        return self._complete(
            source,
            challenge_id,
            secret,
            lambda: None,
            lambda challenge, identity, _: (
                challenge.server_id,
                tickets.issue(
                    challenge.server_id,
                    challenge.generation,
                    VerifiedGameIdentity(identity.playfab_id),
                ),
            ),
        )

    def issue_admission(
        self, source: str, challenge_id: str, secret: str, eos_id_token: str
    ) -> tuple[str, str, int]:
        eos, signing = self.eos, self.signing
        if eos is None or signing is None:
            raise GameIdentityUnavailable("Signed game admissions are disabled")

        def mint(
            challenge: GameJoinChallenge,
            identity: VerifiedGameIdentity,
            platform: VerifiedEosIdentity,
        ) -> tuple[str, str, int]:
            if platform.expires_at <= int(time.time()):
                raise InvalidGameCredential("EOS identity proof expired")
            ticket, expires = signing.issue_game_admission(
                issuer=self.audience,
                server_id=challenge.server_id,
                playfab_id=identity.playfab_id,
                eos=platform,
            )
            return challenge.server_id, ticket, expires

        return self._complete(
            source, challenge_id, secret, lambda: eos.verify(eos_id_token), mint
        )

    def _complete(
        self,
        source: str,
        challenge_id: str,
        secret: str,
        verify_extra: Callable[[], Proof],
        mint: Callable[[GameJoinChallenge, VerifiedGameIdentity, Proof], Issued],
    ) -> Issued:
        source_ip = canonical_address(ip_address(source))
        with self._admit(str(source_ip), "issue"):
            with self._lock:
                challenge = self._challenges.get(challenge_id)
            if (
                challenge is None
                or challenge.expires_at <= int(self.clock())
                or challenge.source != str(source_ip)
                or re.fullmatch(r"[A-Za-z0-9_-]{43}", secret) is None
                or not hmac.compare_digest(
                    challenge.commitment,
                    hashlib.sha256(secret.encode("ascii")).hexdigest(),
                )
            ):
                raise InvalidGameCredential("Account-control challenge rejected")

            with self.registry.join_target(
                source_ip, challenge.target_ip, challenge.target_port
            ) as binding:
                if binding != (challenge.server_id, challenge.generation):
                    raise InvalidJoinRegistration()
            extra = verify_extra()
            identity = self.verifier.verify(challenge.playfab_id, challenge.proof)
            if identity.playfab_id != challenge.playfab_id:
                raise InvalidGameCredential("Account-control identity mismatch")
            # Re-resolve after HTTP. Registration and challenge consumption are
            # coordinated; concurrent completions can mint at most one grant.
            with self.registry.join_target(
                source_ip, challenge.target_ip, challenge.target_port
            ) as binding:
                if binding != (challenge.server_id, challenge.generation):
                    raise InvalidJoinRegistration()
                with self._lock:
                    if self._challenges.get(
                        challenge_id
                    ) is not challenge or challenge.expires_at <= int(self.clock()):
                        raise InvalidGameCredential(
                            "Account-control challenge rejected"
                        )
                    del self._challenges[challenge_id]
                return mint(challenge, identity, extra)

    def redeem(
        self, source: str, server_id: str, key: str, ticket: str, playfab_id: str
    ) -> VerifiedGameIdentity:
        if self.tickets is None:
            raise GameIdentityUnavailable("Online game join redemption is disabled")
        source_ip = canonical_address(ip_address(source))
        with self._admit(str(source_ip), "redeem"):
            with self.registry.join_registration(
                server_id, key, source_ip
            ) as generation:
                return self.tickets.redeem(server_id, generation, ticket, playfab_id)
