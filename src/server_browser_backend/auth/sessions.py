"""Bounded SQLite authentication sessions with atomic opaque-token rotation.

No HTTP/OAuth activation lives here. All workers must use one local database
and identical persisted limits. Network admission/rate limits are separate.
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
from uuid import uuid4

from server_browser_backend.auth.identity import validate_discord_id


class InvalidCredential(Exception):
    """Invalid, expired, or revoked credential. Never contains its value."""


class RefreshReplay(InvalidCredential):
    """Retained spent credential reused; its entire family is now revoked."""


class SessionCapacity(Exception):
    """A resource budget is exhausted; no valid session was evicted."""


class SessionBusy(Exception):
    """Storage is busy; no rotation succeeded. Do not assume a new credential."""


class RefreshTooSoon(Exception):
    def __init__(self, retry_after: int):
        super().__init__("Refresh rotation requested too soon")
        self.retry_after = retry_after


@dataclass(frozen=True)
class SessionLimits:
    sessions: int = 1024
    per_account: int = 4
    credentials: int = 65536
    per_session_credentials: int = 256
    idle_seconds: int = 86400
    absolute_seconds: int = 604800
    rotation_seconds: int = 60
    cleanup_batch: int = 32
    database_pages: int = 16384  # 64 MiB at the enforced 4096-byte page size.

    def __post_init__(self):
        if any(type(value) is not int or value <= 0 for value in asdict(self).values()):
            raise ValueError("Session limits must be positive integers")
        if (
            self.rotation_seconds >= self.idle_seconds
            or self.idle_seconds > self.absolute_seconds
        ):
            raise ValueError(
                "Require rotation interval < idle lifetime <= absolute lifetime"
            )
        if (
            self.per_account > self.sessions
            or self.per_session_credentials > self.credentials
        ):
            raise ValueError("Per-owner quota exceeds the global quota")


@dataclass(frozen=True)
class SessionIdentity:
    session_id: str
    discord_id: str
    auth_time: int
    expires_at: int
    absolute_expires_at: int


@dataclass(frozen=True)
class SessionCredentials:
    identity: SessionIdentity
    credential: str = field(repr=False)


def credential_hash(value: str) -> bytes:
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9_-]{43}", value) is None:
        raise InvalidCredential("Invalid authentication credential")
    return hashlib.sha256(value.encode("ascii")).digest()


class SessionStore:
    def __init__(self, path: Path, limits: SessionLimits = SessionLimits()):
        self.path = path
        self.limits = limits
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(descriptor)
        info = path.stat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Session database must be a regular file")
        if os.name == "posix" and stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError(
                "Session database must not be accessible to group or other users"
            )
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=DELETE")
            if connection.execute("PRAGMA page_size").fetchone()[0] != 4096:
                raise ValueError("Session database requires 4096-byte pages")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), limits_json TEXT NOT NULL)"
            )
            configuration = json.dumps(asdict(limits), sort_keys=True)
            connection.execute(
                "INSERT OR IGNORE INTO settings VALUES (1, ?)", (configuration,)
            )
            if (
                connection.execute(
                    "SELECT limits_json FROM settings WHERE id=1"
                ).fetchone()[0]
                != configuration
            ):
                raise ValueError("Session workers must use identical persisted limits")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, discord_id TEXT NOT NULL, auth_time INTEGER NOT NULL, expires_at INTEGER NOT NULL, absolute_expires_at INTEGER NOT NULL)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS sessions_account ON sessions(discord_id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS credentials (digest BLOB PRIMARY KEY, session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE, issued_at INTEGER NOT NULL, spent_at INTEGER)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS credentials_session ON credentials(session_id)"
            )
            connection.commit()

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.path, timeout=1, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA cache_size=-2048")
            maximum = connection.execute(
                f"PRAGMA max_page_count={self.limits.database_pages}"
            ).fetchone()[0]
            if maximum != self.limits.database_pages:
                raise SessionCapacity("Session database exceeds its storage budget")
            yield connection
        except sqlite3.OperationalError as error:
            code = getattr(error, "sqlite_errorcode", None)
            if code == 13 or str(error) == "database or disk is full":  # SQLITE_FULL
                raise SessionCapacity("Session storage budget exhausted") from None
            if code in (5, 6) or str(error) in {
                "database is locked",
                "database table is locked",
            }:
                raise SessionBusy("Session storage is busy") from None
            raise
        finally:
            connection.close()

    @contextmanager
    def _transaction(self):
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def _cleanup(self, connection: sqlite3.Connection, now: int) -> int:
        ids = [
            row[0]
            for row in connection.execute(
                "SELECT id FROM sessions WHERE expires_at <= ? ORDER BY expires_at LIMIT ?",
                (now, self.limits.cleanup_batch),
            )
        ]
        connection.executemany(
            "DELETE FROM sessions WHERE id=?", [(session_id,) for session_id in ids]
        )
        return len(ids)

    def cleanup(self) -> int:
        with self._transaction() as connection:
            return self._cleanup(connection, int(time.time()))

    @contextmanager
    def _maintained_transaction(self):
        rejection = None
        with self._transaction() as connection:
            now = int(time.time())
            self._cleanup(connection, now)
            connection.execute("SAVEPOINT request")
            try:
                yield connection, now
            except (SessionCapacity, RefreshTooSoon) as error:
                # Keep bounded cleanup progress, but never partial request changes.
                connection.execute("ROLLBACK TO request")
                rejection = error
            connection.execute("RELEASE request")
        if rejection is not None:
            raise rejection

    def create(self, discord_id: str, auth_time: int) -> SessionCredentials:
        validate_discord_id(discord_id)
        if type(auth_time) is not int or not 0 < auth_time <= int(time.time()):
            raise ValueError("Invalid authentication time")
        with self._maintained_transaction() as (connection, now):
            total = connection.execute(
                "SELECT count(*) FROM sessions WHERE expires_at > ?", (now,)
            ).fetchone()[0]
            account = connection.execute(
                "SELECT count(*) FROM sessions WHERE discord_id=? AND expires_at > ?",
                (discord_id, now),
            ).fetchone()[0]
            if total >= self.limits.sessions or account >= self.limits.per_account:
                raise SessionCapacity("Session count budget exhausted")
            self._check_credential_capacity(connection)
            identity = SessionIdentity(
                str(uuid4()),
                discord_id,
                auth_time,
                now + self.limits.idle_seconds,
                now + self.limits.absolute_seconds,
            )
            credential = secrets.token_urlsafe(32)
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                tuple(asdict(identity).values()),
            )
            connection.execute(
                "INSERT INTO credentials VALUES (?, ?, ?, NULL)",
                (credential_hash(credential), identity.session_id, now),
            )
            return SessionCredentials(identity, credential)

    def _check_credential_capacity(
        self, connection: sqlite3.Connection, session_id: str | None = None
    ) -> None:
        if (
            connection.execute("SELECT count(*) FROM credentials").fetchone()[0]
            >= self.limits.credentials
        ):
            raise SessionCapacity("Credential history budget exhausted")
        if (
            session_id is not None
            and connection.execute(
                "SELECT count(*) FROM credentials WHERE session_id=?", (session_id,)
            ).fetchone()[0]
            >= self.limits.per_session_credentials
        ):
            raise SessionCapacity(
                "Session rotation budget exhausted; reauthentication required"
            )

    def _use(
        self, credential: str, *, rotate: bool
    ) -> SessionCredentials | SessionIdentity:
        digest = credential_hash(credential)  # Invalid shapes allocate no DB state.
        replay = False
        result: SessionCredentials | SessionIdentity | None = None
        with self._maintained_transaction() as (connection, now):
            row = connection.execute(
                "SELECT s.*, c.issued_at, c.spent_at FROM credentials c JOIN sessions s ON s.id=c.session_id WHERE c.digest=? AND s.expires_at > ?",
                (digest, now),
            ).fetchone()
            if row is not None:
                if row["spent_at"] is not None:
                    connection.execute("DELETE FROM sessions WHERE id=?", (row["id"],))
                    replay = True  # Commit family revocation before raising.
                else:
                    if rotate:
                        wait = row["issued_at"] + self.limits.rotation_seconds - now
                        if wait > 0:
                            raise RefreshTooSoon(wait)
                        self._check_credential_capacity(connection, row["id"])
                    expiry = min(
                        now + self.limits.idle_seconds, row["absolute_expires_at"]
                    )
                    connection.execute(
                        "UPDATE sessions SET expires_at=? WHERE id=?",
                        (expiry, row["id"]),
                    )
                    identity = SessionIdentity(
                        row["id"],
                        row["discord_id"],
                        row["auth_time"],
                        expiry,
                        row["absolute_expires_at"],
                    )
                    if rotate:
                        replacement = secrets.token_urlsafe(32)
                        connection.execute(
                            "UPDATE credentials SET spent_at=? WHERE digest=?",
                            (now, digest),
                        )
                        connection.execute(
                            "INSERT INTO credentials VALUES (?, ?, ?, NULL)",
                            (credential_hash(replacement), row["id"], now),
                        )
                        result = SessionCredentials(identity, replacement)
                    else:
                        result = identity
        if replay:
            raise RefreshReplay("Credential reuse revoked the authentication session")
        if result is None:
            raise InvalidCredential("Invalid authentication credential")
        return result

    def authenticate(self, credential: str) -> SessionIdentity:
        result = self._use(credential, rotate=False)
        assert isinstance(result, SessionIdentity)
        return result

    def refresh(self, credential: str) -> SessionCredentials:
        result = self._use(credential, rotate=True)
        assert isinstance(result, SessionCredentials)
        return result

    def logout(self, credential: str) -> None:
        digest = credential_hash(credential)
        with self._transaction() as connection:
            connection.execute(
                "DELETE FROM sessions WHERE id=(SELECT session_id FROM credentials WHERE digest=?)",
                (digest,),
            )
