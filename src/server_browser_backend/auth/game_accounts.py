"""Persistent first-use pins for independently verified identities, not provider links.

All workers share this private database. Never automatically evict or replace
pins. Recovery and privacy requests require an explicit operator workflow;
see docs/game-account-linkage.md and docs/player-identity-privacy.md.
"""

from __future__ import annotations

import hmac
import json
import os
import re
import sqlite3
import stat
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, TypeVar
from uuid import UUID, uuid4

from server_browser_backend.auth.account_digests import (
    FORMAT,
    AccountDigester,
    provision_key,
)
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
        digester: AccountDigester,
        limits: AccountLimits = AccountLimits(),
        *,
        clock: Callable[[], float] = time.time,
    ):
        self.path, self.limits, self.clock = path, limits, clock
        self.digester = digester
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
            existing = db.execute("PRAGMA table_info(account_settings)").fetchall()
            tables = {
                row["name"]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            identity_tables = {"user_accounts", "validated_mismatches"}
            if (existing and not identity_tables.issubset(tables)) or (
                not existing and identity_tables.intersection(tables)
            ):
                raise ValueError(
                    "Incomplete account schema; restore or explicitly migrate the database"
                )
            if existing and {row["name"] for row in existing} != {
                "id",
                "limits_json",
                "identity_format",
                "key_check",
            }:
                raise ValueError(
                    "Plaintext account database requires explicit offline migration"
                )
            db.execute(
                "CREATE TABLE IF NOT EXISTS account_settings (id INTEGER PRIMARY KEY CHECK(id=1), limits_json TEXT NOT NULL, identity_format TEXT NOT NULL, key_check BLOB NOT NULL)"
            )
            settings = json.dumps(asdict(limits), sort_keys=True)
            if (
                existing
                and db.execute("SELECT id FROM account_settings WHERE id=1").fetchone()
                is None
            ):
                raise ValueError("Missing account key binding; restore the database")
            db.execute(
                "INSERT OR IGNORE INTO account_settings VALUES (1, ?, ?, ?)",
                (settings, FORMAT, digester.key_check),
            )
            if (
                db.execute(
                    "SELECT limits_json FROM account_settings WHERE id=1"
                ).fetchone()[0]
                != settings
            ):
                raise ValueError("Account workers must use identical persisted limits")
            configuration = db.execute(
                "SELECT identity_format, key_check FROM account_settings WHERE id=1"
            ).fetchone()
            if (
                configuration["identity_format"] != FORMAT
                or type(configuration["key_check"]) is not bytes
                or not hmac.compare_digest(
                    configuration["key_check"], digester.key_check
                )
            ):
                raise ValueError(
                    "Account digest format or key does not match the database"
                )
            db.execute("""CREATE TABLE IF NOT EXISTS user_accounts (
                id TEXT PRIMARY KEY, playfab_digest BLOB NOT NULL UNIQUE CHECK(length(playfab_digest)=32),
                steam_digest BLOB UNIQUE CHECK(steam_digest IS NULL OR length(steam_digest)=32),
                eos_digest BLOB NOT NULL UNIQUE CHECK(length(eos_digest)=32),
                first_login_date INTEGER NOT NULL, last_login_date INTEGER NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS validated_mismatches (
                id TEXT PRIMARY KEY, playfab_digest BLOB NOT NULL CHECK(length(playfab_digest)=32),
                steam_digest BLOB CHECK(steam_digest IS NULL OR length(steam_digest)=32),
                eos_digest BLOB NOT NULL CHECK(length(eos_digest)=32), reason TEXT NOT NULL,
                first_mismatch_date INTEGER NOT NULL, last_mismatch_date INTEGER NOT NULL,
                occurrence_count INTEGER NOT NULL
            )""")
            # SQLite normally treats NULLs as distinct; Epic retries must deduplicate.
            db.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS mismatch_combination ON validated_mismatches(playfab_digest, COALESCE(steam_digest, X''), eos_digest)"
            )
            for table, expected in {
                "user_accounts": {
                    "id",
                    "playfab_digest",
                    "steam_digest",
                    "eos_digest",
                    "first_login_date",
                    "last_login_date",
                },
                "validated_mismatches": {
                    "id",
                    "playfab_digest",
                    "steam_digest",
                    "eos_digest",
                    "reason",
                    "first_mismatch_date",
                    "last_mismatch_date",
                    "occurrence_count",
                },
            }.items():
                if {
                    row["name"] for row in db.execute(f"PRAGMA table_info({table})")
                } != expected:
                    raise ValueError("Unsupported account digest schema")

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
        pf, steam_digest, eos = self.identity_digests(
            identity.playfab_id, steam, platform.product_user_id
        )
        now = int(self.clock())
        mismatch = False
        with self._transaction() as db:
            matches = db.execute(
                "SELECT * FROM user_accounts WHERE playfab_digest=? OR eos_digest=? OR steam_digest=?",
                (pf, eos, steam_digest),
            ).fetchall()
            account = next(
                (row for row in matches if row["playfab_digest"] == pf), None
            )
            mismatch = any(
                row["playfab_digest"] != pf
                or row["eos_digest"] != eos
                or (
                    steam_digest is not None
                    and row["steam_digest"] not in (None, steam_digest)
                )
                for row in matches
            )
            if mismatch:
                existing = db.execute(
                    "SELECT id FROM validated_mismatches WHERE playfab_digest=? AND steam_digest IS ? AND eos_digest=?",
                    (pf, steam_digest, eos),
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
                            steam_digest,
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
                        "UPDATE user_accounts SET steam_digest=COALESCE(steam_digest, ?), last_login_date=MAX(last_login_date, ?) WHERE id=?",
                        (steam_digest, now, account["id"]),
                    )
                else:
                    if (
                        db.execute("SELECT count(*) FROM user_accounts").fetchone()[0]
                        >= self.limits.accounts
                    ):
                        raise GameIdentityUnavailable("Account pin capacity exhausted")
                    db.execute(
                        "INSERT INTO user_accounts VALUES (?, ?, ?, ?, ?, ?)",
                        (str(uuid4()), pf, steam_digest, eos, now, now),
                    )
                result = mint()
        if mismatch:
            raise AccountMismatch("Account Mismatch")
        return result

    def identity_digests(
        self, playfab: str, steam: str | None, eos: str
    ) -> tuple[bytes, bytes | None, bytes]:
        """Canonical IDs only; useful for scoped operator lookups, not a public API."""
        identity = VerifiedGameIdentity(playfab, steam)
        if not isinstance(eos, str) or re.fullmatch(r"[0-9a-f]{32}", eos) is None:
            raise ValueError("Invalid EOS identity")
        return (
            self.digester.digest("playfab", identity.playfab_id),
            self.digester.digest("steam", steam) if steam is not None else None,
            self.digester.digest("eos", eos),
        )


def migrate_plaintext(
    source: Path, destination: Path, digester: AccountDigester
) -> None:
    """Offline copy migration. Never modify the source or overwrite a destination.

    Publish only a fully committed digest database. The source and its backups
    remain sensitive; overwriting rows in place would leave plaintext remnants.
    """
    info = source.lstat()
    if not stat.S_ISREG(info.st_mode) or (
        os.name == "posix" and stat.S_IMODE(info.st_mode) & 0o077
    ):
        raise ValueError("Migration source must be a private regular file")
    if os.path.lexists(destination):
        raise FileExistsError("Migration destination already exists")
    original = sqlite3.connect(
        source.absolute().as_uri() + "?mode=ro",
        uri=True,
        timeout=1,
        isolation_level=None,
    )
    original.row_factory = sqlite3.Row
    temporary = None
    try:
        original.execute("BEGIN")
        columns = {
            row["name"]
            for row in original.execute("PRAGMA table_info(account_settings)")
        }
        if columns != {"id", "limits_json"}:
            raise ValueError("Migration requires the legacy plaintext account schema")
        settings = original.execute(
            "SELECT limits_json FROM account_settings WHERE id=1"
        ).fetchone()
        limits = AccountLimits(**json.loads(settings["limits_json"]))
        descriptor, name = tempfile.mkstemp(
            prefix=".account-migration-", dir=destination.parent
        )
        os.close(descriptor)
        temporary = Path(name)
        target = GameAccountStore(temporary, digester, limits)
        with target._transaction() as db:
            for table in ("user_accounts", "validated_mismatches"):
                maximum = (
                    limits.accounts if table == "user_accounts" else limits.mismatches
                )
                count = 0
                for row in original.execute(f"SELECT * FROM {table}"):
                    count += 1
                    if count > maximum:
                        raise ValueError("Migration source exceeds account limits")
                    if str(UUID(row["id"])) != row["id"]:
                        raise ValueError("Invalid account record UUID")
                    pf, steam, eos = target.identity_digests(
                        row["playfab_id"], row["steam_id"], row["eos_id"]
                    )
                    first = (
                        row["first_login_date"]
                        if table == "user_accounts"
                        else row["first_mismatch_date"]
                    )
                    last = (
                        row["last_login_date"]
                        if table == "user_accounts"
                        else row["last_mismatch_date"]
                    )
                    if (
                        type(first) is not int
                        or type(last) is not int
                        or not 0 <= first <= last
                    ):
                        raise ValueError("Invalid account record dates")
                    if table == "user_accounts":
                        db.execute(
                            "INSERT INTO user_accounts VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                row["id"],
                                pf,
                                steam,
                                eos,
                                row["first_login_date"],
                                row["last_login_date"],
                            ),
                        )
                    else:
                        if row["reason"] != "identity_conflict":
                            raise ValueError("Unsupported mismatch reason")
                        if (
                            type(row["occurrence_count"]) is not int
                            or row["occurrence_count"] < 1
                        ):
                            raise ValueError("Invalid mismatch count")
                        db.execute(
                            "INSERT INTO validated_mismatches VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                row["id"],
                                pf,
                                steam,
                                eos,
                                row["reason"],
                                row["first_mismatch_date"],
                                row["last_mismatch_date"],
                                row["occurrence_count"],
                            ),
                        )
        # Atomic publication without replacing any existing file, even if another
        # migration raced the preflight check. Temp file is on the same filesystem.
        os.link(temporary, destination)
        directory = os.open(destination.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        original.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Provision account HMAC keys or migrate a stopped plaintext account database."
    )
    commands = parser.add_subparsers(dest="action", required=True)
    init = commands.add_parser("init-key")
    init.add_argument("path", type=Path)
    migration = commands.add_parser("migrate")
    migration.add_argument("source", type=Path)
    migration.add_argument("destination", type=Path)
    migration.add_argument("--key", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "init-key":
        provision_key(args.path)
    else:
        migrate_plaintext(args.source, args.destination, AccountDigester.load(args.key))


if __name__ == "__main__":
    main()
