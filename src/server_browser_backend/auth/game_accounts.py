"""Persistent first-use pins for independently verified identities, not provider links.

All workers share this private database. Never evict pins or automatically
replace them: recovery requires an operator-reviewed correction while stopped.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import stat
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, TypeVar
from uuid import uuid4

from server_browser_backend.auth.eos_identity import VerifiedEosIdentity
from server_browser_backend.auth.game_identity import (
    GameIdentityUnavailable,
    VerifiedGameIdentity,
)

Result = TypeVar("Result")


class AccountMismatch(Exception):
    """Both proofs validated, but their combination conflicts with a durable pin."""


@dataclass(frozen=True)
class AccountLimits:
    accounts: int = 100_000
    mismatches: int = 100_000
    database_pages: int = 16_384

    def __post_init__(self):
        if any(type(value) is not int or value <= 0 for value in asdict(self).values()):
            raise ValueError("Account storage limits must be positive integers")


class GameAccountStore:
    def __init__(
        self,
        path: Path,
        limits: AccountLimits = AccountLimits(),
        *,
        clock: Callable[[], float] = time.time,
    ):
        self.path, self.limits, self.clock = path, limits, clock
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
            raise ValueError("Account database must be a private regular file")
        with self._transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS account_settings (id INTEGER PRIMARY KEY CHECK(id=1), limits_json TEXT NOT NULL)"
            )
            settings = json.dumps(asdict(limits), sort_keys=True)
            db.execute(
                "INSERT OR IGNORE INTO account_settings VALUES (1, ?)", (settings,)
            )
            if (
                db.execute(
                    "SELECT limits_json FROM account_settings WHERE id=1"
                ).fetchone()[0]
                != settings
            ):
                raise ValueError("Account workers must use identical persisted limits")
            db.execute("""CREATE TABLE IF NOT EXISTS user_accounts (
                id TEXT PRIMARY KEY, playfab_id TEXT NOT NULL UNIQUE,
                steam_id TEXT UNIQUE, eos_id TEXT NOT NULL UNIQUE,
                first_login_date INTEGER NOT NULL, last_login_date INTEGER NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS validated_mismatches (
                id TEXT PRIMARY KEY, playfab_id TEXT NOT NULL, steam_id TEXT,
                eos_id TEXT NOT NULL, reason TEXT NOT NULL,
                first_mismatch_date INTEGER NOT NULL, last_mismatch_date INTEGER NOT NULL,
                occurrence_count INTEGER NOT NULL
            )""")
            # SQLite normally treats NULLs as distinct; Epic retries must deduplicate.
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS mismatch_combination ON validated_mismatches(playfab_id, COALESCE(steam_id, ''), eos_id)"
            )

    @contextmanager
    def _transaction(self):
        try:
            db = sqlite3.connect(self.path, timeout=1, isolation_level=None)
        except sqlite3.Error:
            raise GameIdentityUnavailable("Account storage unavailable") from None
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA cache_size=-1024")
            maximum = db.execute(
                f"PRAGMA max_page_count={self.limits.database_pages}"
            ).fetchone()[0]
            if maximum != self.limits.database_pages:
                raise GameIdentityUnavailable("Account storage exceeds budget")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except sqlite3.Error:
            db.rollback()
            raise GameIdentityUnavailable("Account storage unavailable") from None
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def admit(
        self,
        identity: VerifiedGameIdentity,
        platform: VerifiedEosIdentity,
        mint: Callable[[], Result],
    ) -> Result:
        """Pin/check verified IDs and mint in one transaction; no network callbacks.

        A signing failure rolls back pin/login changes. A mismatch is committed
        before raising, so rejection cannot roll back its audit record.
        """
        if not isinstance(identity, VerifiedGameIdentity) or not isinstance(
            platform, VerifiedEosIdentity
        ):
            raise ValueError("Verified account identities required")
        if (
            not isinstance(platform.product_user_id, str)
            or re.fullmatch(r"[0-9a-f]{32}", platform.product_user_id) is None
        ):
            raise ValueError("Invalid verified EOS identity")
        steam = platform.platform_id if platform.platform_provider == "steam" else None
        if platform.platform_provider == "steam":
            if steam is None or identity.linked_steam_id != steam:
                raise ValueError("Verified Steam association required")
            VerifiedGameIdentity(identity.playfab_id, steam)
        elif (
            platform.platform_provider != "eos"
            or platform.platform_id != platform.product_user_id
        ):
            raise ValueError("Unsupported verified platform identity")
        pf, eos, now = identity.playfab_id, platform.product_user_id, int(self.clock())
        mismatch = False
        with self._transaction() as db:
            matches = db.execute(
                "SELECT * FROM user_accounts WHERE playfab_id=? OR eos_id=? OR steam_id=?",
                (pf, eos, steam),
            ).fetchall()
            account = next((row for row in matches if row["playfab_id"] == pf), None)
            mismatch = any(
                row["playfab_id"] != pf
                or row["eos_id"] != eos
                or (steam is not None and row["steam_id"] not in (None, steam))
                for row in matches
            )
            if mismatch:
                existing = db.execute(
                    "SELECT id FROM validated_mismatches WHERE playfab_id=? AND steam_id IS ? AND eos_id=?",
                    (pf, steam, eos),
                ).fetchone()
                if existing:
                    db.execute(
                        "UPDATE validated_mismatches SET last_mismatch_date=MAX(last_mismatch_date, ?), occurrence_count=occurrence_count+1 WHERE id=?",
                        (now, existing["id"]),
                    )
                else:
                    if (
                        db.execute(
                            "SELECT count(*) FROM validated_mismatches"
                        ).fetchone()[0]
                        >= self.limits.mismatches
                    ):
                        raise GameIdentityUnavailable(
                            "Account mismatch audit capacity exhausted"
                        )
                    db.execute(
                        "INSERT INTO validated_mismatches VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            str(uuid4()),
                            pf,
                            steam,
                            eos,
                            "identity_conflict",
                            now,
                            now,
                            1,
                        ),
                    )
            else:
                if account:
                    db.execute(
                        "UPDATE user_accounts SET steam_id=COALESCE(steam_id, ?), last_login_date=MAX(last_login_date, ?) WHERE id=?",
                        (steam, now, account["id"]),
                    )
                else:
                    if (
                        db.execute("SELECT count(*) FROM user_accounts").fetchone()[0]
                        >= self.limits.accounts
                    ):
                        raise GameIdentityUnavailable("Account pin capacity exhausted")
                    db.execute(
                        "INSERT INTO user_accounts VALUES (?, ?, ?, ?, ?, ?)",
                        (str(uuid4()), pf, steam, eos, now, now),
                    )
                result = mint()
        if mismatch:
            raise AccountMismatch("Account Mismatch")
        return result
