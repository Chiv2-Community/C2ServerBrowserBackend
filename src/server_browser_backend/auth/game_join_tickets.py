"""Bounded, single-use game join grants behind live-registration authentication.

The caller must authenticate the live server registration before redemption.
Its generation is SHA-256 of that registration's secret key, never a client claim.
All workers must share this database and limits. Lost redemption responses require
a new ticket; retrying a spent ticket never grants a second admission.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import stat
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from server_browser_backend.auth.game_identity import VerifiedGameIdentity


class InvalidGameJoinTicket(Exception):
    pass


class GameJoinCapacity(Exception):
    pass


class GameJoinBusy(Exception):
    pass


@dataclass(frozen=True)
class GameJoinLimits:
    tickets: int = 4096
    per_account: int = 4
    lifetime_seconds: int = 60
    cleanup_batch: int = 32
    database_pages: int = 1024

    def __post_init__(self):
        if any(type(value) is not int or value <= 0 for value in asdict(self).values()):
            raise ValueError("Game join limits must be positive integers")
        if self.per_account > self.tickets or self.lifetime_seconds > 300:
            raise ValueError("Invalid game join limits")


@dataclass(frozen=True)
class GameJoinTicket:
    credential: str = field(repr=False)
    expires_at: int


def _binding(server_id: str, registration_generation: bytes) -> None:
    if (
        not isinstance(server_id, str)
        or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", server_id) is None
    ):
        raise ValueError("Invalid game server identity")
    if type(registration_generation) is not bytes or len(registration_generation) != 32:
        raise ValueError("Invalid registration generation")


def _digest(credential: str) -> bytes:
    if (
        not isinstance(credential, str)
        or re.fullmatch(r"[A-Za-z0-9_-]{43}", credential) is None
    ):
        raise InvalidGameJoinTicket("Invalid game join ticket")
    return hashlib.sha256(credential.encode("ascii")).digest()


class GameJoinTicketStore:
    def __init__(
        self,
        path: Path,
        limits: GameJoinLimits = GameJoinLimits(),
        *,
        clock: Callable[[], float] = time.time,
    ):
        self.path = path
        self.limits = limits
        self.clock = clock
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(descriptor)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or (
            os.name == "posix" and stat.S_IMODE(info.st_mode) & 0o077
        ):
            raise ValueError("Game join database must be a private regular file")
        with self._transaction() as connection:
            if connection.execute("PRAGMA page_size").fetchone()[0] != 4096:
                raise ValueError("Game join database requires 4096-byte pages")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS game_join_settings (id INTEGER PRIMARY KEY CHECK(id=1), limits_json TEXT NOT NULL)"
            )
            configuration = json.dumps(asdict(limits), sort_keys=True)
            connection.execute(
                "INSERT OR IGNORE INTO game_join_settings VALUES (1, ?)",
                (configuration,),
            )
            if (
                connection.execute(
                    "SELECT limits_json FROM game_join_settings WHERE id=1"
                ).fetchone()[0]
                != configuration
            ):
                raise ValueError(
                    "Game join workers must use identical persisted limits"
                )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS game_join_tickets (digest BLOB PRIMARY KEY, server_id TEXT NOT NULL, generation BLOB NOT NULL, playfab_id TEXT NOT NULL, steam_id TEXT, expires_at INTEGER NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS game_join_expiry ON game_join_tickets(expires_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS game_join_account ON game_join_tickets(playfab_id)"
            )

    @contextmanager
    def _transaction(self):
        connection = sqlite3.connect(self.path, timeout=1, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=DELETE")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA cache_size=-1024")
            maximum = connection.execute(
                f"PRAGMA max_page_count={self.limits.database_pages}"
            ).fetchone()[0]
            if maximum != self.limits.database_pages:
                raise GameJoinCapacity("Game join storage exceeds budget")
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except sqlite3.OperationalError as error:
            connection.rollback()
            code = getattr(error, "sqlite_errorcode", None)
            if code in (5, 6):
                raise GameJoinBusy("Game join storage busy") from None
            if code == 13:
                raise GameJoinCapacity("Game join storage full") from None
            raise
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _cleanup(self, connection: sqlite3.Connection, now: int) -> None:
        connection.execute(
            "DELETE FROM game_join_tickets WHERE digest IN (SELECT digest FROM game_join_tickets WHERE expires_at <= ? ORDER BY expires_at LIMIT ?)",
            (now, self.limits.cleanup_batch),
        )

    def issue(
        self,
        server_id: str,
        registration_generation: bytes,
        identity: VerifiedGameIdentity,
    ) -> GameJoinTicket:
        _binding(server_id, registration_generation)
        if not isinstance(identity, VerifiedGameIdentity):
            raise ValueError("Verified game identity required")
        now = int(self.clock())
        ticket = GameJoinTicket(
            secrets.token_urlsafe(32), now + self.limits.lifetime_seconds
        )
        full = False
        with self._transaction() as connection:
            self._cleanup(connection, now)
            full = (
                connection.execute("SELECT count(*) FROM game_join_tickets").fetchone()[
                    0
                ]
                >= self.limits.tickets
                or connection.execute(
                    "SELECT count(*) FROM game_join_tickets WHERE playfab_id=? AND expires_at>?",
                    (identity.playfab_id, now),
                ).fetchone()[0]
                >= self.limits.per_account
            )
            if not full:
                connection.execute(
                    "INSERT INTO game_join_tickets VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        _digest(ticket.credential),
                        server_id,
                        registration_generation,
                        identity.playfab_id,
                        identity.linked_steam_id,
                        ticket.expires_at,
                    ),
                )
        # Commit bounded expired-row cleanup even when admission was rejected.
        if full:
            raise GameJoinCapacity("Game join ticket budget exhausted")
        return ticket

    def redeem(
        self,
        server_id: str,
        registration_generation: bytes,
        credential: str,
        claimed_playfab_id: str,
    ) -> VerifiedGameIdentity:
        _binding(server_id, registration_generation)
        digest = _digest(credential)
        try:
            claim = VerifiedGameIdentity(claimed_playfab_id).playfab_id
        except ValueError:
            raise InvalidGameJoinTicket("Invalid game join ticket") from None
        now = int(self.clock())
        with self._transaction() as connection:
            self._cleanup(connection, now)
            row = connection.execute(
                "SELECT playfab_id, steam_id FROM game_join_tickets WHERE digest=? AND server_id=? AND generation=? AND playfab_id=? AND expires_at>?",
                (digest, server_id, registration_generation, claim, now),
            ).fetchone()
            if row is not None:
                connection.execute(
                    "DELETE FROM game_join_tickets WHERE digest=?", (digest,)
                )
        if row is None:
            raise InvalidGameJoinTicket("Invalid game join ticket")
        return VerifiedGameIdentity(row["playfab_id"], row["steam_id"])
