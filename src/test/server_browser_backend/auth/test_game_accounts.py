import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from uuid import UUID

import pytest

from server_browser_backend.auth.account_digests import AccountDigester
from server_browser_backend.auth.eos_identity import VerifiedEosIdentity
from server_browser_backend.auth.game_accounts import (
    AccountLimits,
    AccountMismatch,
    GameAccountStore,
)
from server_browser_backend.auth.game_identity import (
    GameIdentityUnavailable,
    VerifiedGameIdentity,
)

STEAM = "76561197993652680"
DIGESTER = AccountDigester(b"k" * 32)


def eos(puid="a" * 32, steam=None):
    return VerifiedEosIdentity(
        puid, "steam" if steam else "eos", steam or puid, int(time.time()) + 300
    )


def login(store, pf="ABC123", puid="a" * 32, steam=None, mint=lambda: "signed"):
    return store.admit(VerifiedGameIdentity(pf, steam), eos(puid, steam), mint)


def rows(store, table):
    with sqlite3.connect(store.path) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(f"SELECT * FROM {table}")]


def test_pin_persists_across_restart_and_matching_login_updates_only_last_date(
    tmp_path,
):
    path = tmp_path / "accounts.sqlite"
    store = GameAccountStore(path, DIGESTER, clock=lambda: 100)
    assert login(store) == "signed"
    first = rows(store, "user_accounts")[0]
    UUID(first["id"])
    assert first["steam_digest"] is None
    assert first["first_login_date"] == first["last_login_date"] == 100
    restarted = GameAccountStore(path, DIGESTER, clock=lambda: 200)
    login(restarted, pf="abc123")
    assert rows(store, "user_accounts") == [{**first, "last_login_date": 200}]
    assert rows(store, "validated_mismatches") == []
    if os.name == "posix":
        assert path.stat().st_mode & 0o077 == 0


@pytest.mark.parametrize(
    "change",
    [
        {"puid": "b" * 32},
        {"pf": "DEF456"},
        {"steam": "76561197993652681"},
        {"pf": "DEF456", "puid": "b" * 32},
    ],
)
def test_conflicts_audit_after_commit_and_never_mutate_pin(tmp_path, change):
    store = GameAccountStore(tmp_path / "db", DIGESTER, clock=lambda: 100)
    login(store, steam=STEAM)
    first = rows(store, "user_accounts")
    for now in (200, 300):
        store.clock = lambda: now
        with pytest.raises(AccountMismatch, match="Account Mismatch"):
            login(store, **({"steam": STEAM} | change))
    assert rows(store, "user_accounts") == first
    mismatch = rows(store, "validated_mismatches")[0]
    UUID(mismatch["id"])
    assert mismatch["first_mismatch_date"] == 200
    assert mismatch["last_mismatch_date"] == 300
    assert mismatch["occurrence_count"] == 2


def test_null_steam_mismatches_are_deduplicated(tmp_path):
    store = GameAccountStore(tmp_path / "db", DIGESTER)
    login(store)
    for _ in range(3):
        with pytest.raises(AccountMismatch):
            login(store, puid="b" * 32)
    assert len(rows(store, "validated_mismatches")) == 1
    assert rows(store, "validated_mismatches")[0]["occurrence_count"] == 3


def test_steam_can_be_added_only_to_the_same_pair_and_is_not_erased(tmp_path):
    store = GameAccountStore(tmp_path / "db", DIGESTER)
    login(store)
    login(store, steam=STEAM)
    login(store)
    assert rows(store, "user_accounts")[0]["steam_digest"] == DIGESTER.digest(
        "steam", STEAM
    )
    with pytest.raises(AccountMismatch):
        login(store, pf="DEF456", puid="b" * 32, steam=STEAM)
    assert len(rows(store, "user_accounts")) == 1


def test_simultaneous_first_use_can_pin_only_one_conflicting_pair(tmp_path):
    path = tmp_path / "db"
    stores = [GameAccountStore(path, DIGESTER), GameAccountStore(path, DIGESTER)]
    barrier = Barrier(2)

    def attempt(index):
        barrier.wait()
        try:
            return login(stores[index], puid=("a" if index else "b") * 32)
        except AccountMismatch:
            return "mismatch"

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(attempt, range(2))) == ["mismatch", "signed"]
    assert len(rows(stores[0], "user_accounts")) == 1
    assert len(rows(stores[0], "validated_mismatches")) == 1


def test_signing_failure_rolls_back_first_pin_and_last_login(tmp_path):
    store = GameAccountStore(tmp_path / "db", DIGESTER, clock=lambda: 100)

    def fail():
        raise GameIdentityUnavailable("signer unavailable")

    with pytest.raises(GameIdentityUnavailable):
        login(store, mint=fail)
    assert rows(store, "user_accounts") == []
    login(store)
    store.clock = lambda: 200
    with pytest.raises(GameIdentityUnavailable):
        login(store, mint=fail)
    assert rows(store, "user_accounts")[0]["last_login_date"] == 100


def test_capacity_fails_closed_without_evicting_pins_or_audit(tmp_path):
    store = GameAccountStore(
        tmp_path / "db", DIGESTER, AccountLimits(accounts=1, mismatches=1)
    )
    login(store)
    with pytest.raises(GameIdentityUnavailable):
        login(store, pf="DEF456", puid="b" * 32)
    with pytest.raises(AccountMismatch):
        login(store, puid="b" * 32)
    with pytest.raises(GameIdentityUnavailable):
        login(store, puid="c" * 32)
    with pytest.raises(AccountMismatch):
        login(store, puid="b" * 32)
    assert (
        len(rows(store, "user_accounts"))
        == len(rows(store, "validated_mismatches"))
        == 1
    )
    assert rows(store, "validated_mismatches")[0]["occurrence_count"] == 2


def test_workers_cannot_disagree_on_persisted_limits(tmp_path):
    path = tmp_path / "db"
    GameAccountStore(path, DIGESTER)
    with pytest.raises(ValueError, match="identical persisted limits"):
        GameAccountStore(path, DIGESTER, AccountLimits(accounts=2))


@pytest.mark.parametrize("kind", ["public", "symlink"])
def test_refuses_unsafe_database_file(tmp_path, kind):
    if os.name != "posix":
        pytest.skip("POSIX file permissions")
    path = tmp_path / "db"
    if kind == "public":
        path.touch(mode=0o644)
    else:
        target = tmp_path / "target"
        target.touch(mode=0o600)
        path.symlink_to(target)
    with pytest.raises(ValueError, match="private regular file"):
        GameAccountStore(path, DIGESTER)


def test_storage_failure_does_not_issue_admission(tmp_path):
    from unittest.mock import Mock

    store = GameAccountStore(tmp_path / "db", DIGESTER)
    store.path.unlink()
    store.path.mkdir()
    mint = Mock()
    with pytest.raises(GameIdentityUnavailable):
        login(store, mint=mint)
    mint.assert_not_called()


def test_unverified_steam_pair_cannot_be_pinned(tmp_path):
    store = GameAccountStore(tmp_path / "db", DIGESTER)
    with pytest.raises(ValueError, match="Verified Steam association required"):
        store.admit(VerifiedGameIdentity("ABC123"), eos(steam=STEAM), lambda: "signed")
    assert rows(store, "user_accounts") == []
