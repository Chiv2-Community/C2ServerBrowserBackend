import hashlib
import hmac
import json
import os
import sqlite3
from uuid import uuid4

import pytest

from server_browser_backend.auth.account_digests import AccountDigester, provision_key
from server_browser_backend.auth.eos_identity import VerifiedEosIdentity
from server_browser_backend.auth.game_accounts import (
    AccountLimits,
    AccountMismatch,
    GameAccountStore,
    migrate_plaintext,
)
from server_browser_backend.auth.game_identity import VerifiedGameIdentity

KEY = bytes(range(32))
PF = "DEADBEEF01234567"
EOS = "1234567890abcdef1234567890abcdef"
STEAM = "76561198012345678"


def admit(store, pf=PF, eos=EOS, steam=STEAM):
    return store.admit(
        VerifiedGameIdentity(pf, steam),
        VerifiedEosIdentity(eos, "steam" if steam else "eos", steam or eos, 9999999999),
        lambda: "signed",
    )


def test_digest_is_deterministic_domain_separated_hmac():
    digester = AccountDigester(KEY)
    expected = hmac.new(
        KEY, b"unchained-account-id-v1\0playfab\0" + PF.encode(), hashlib.sha256
    ).digest()
    assert digester.digest("playfab", PF) == expected
    assert AccountDigester(KEY).digest("playfab", PF) == expected
    assert (
        len({digester.digest(provider, PF) for provider in ("playfab", "steam", "eos")})
        == 3
    )
    assert AccountDigester(b"x" * 32).digest("playfab", PF) != expected
    assert digester.key_check != expected
    assert repr(KEY) not in repr(digester)
    with pytest.raises(ValueError):
        digester.digest("untrusted", PF)


def test_key_is_explicit_private_persistent_and_never_overwritten(tmp_path):
    path = tmp_path / "account.key"
    with pytest.raises(FileNotFoundError):
        AccountDigester.load(path)
    provision_key(path)
    original = path.read_bytes()
    assert len(original) == 32
    assert AccountDigester.load(path).digest("eos", EOS) == AccountDigester.load(
        path
    ).digest("eos", EOS)
    if os.name == "posix":
        assert path.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        provision_key(path)
    assert path.read_bytes() == original


@pytest.mark.parametrize("size", [0, 16, 31, 33, 8192])
def test_invalid_key_length_is_rejected_without_echoing_contents(tmp_path, size):
    path = tmp_path / "key"
    path.touch(mode=0o600)
    path.write_bytes(b"s" * size)
    with pytest.raises(ValueError, match="exactly 32 bytes"):
        AccountDigester.load(path)


@pytest.mark.parametrize("kind", ["public", "symlink", "directory", "fifo"])
def test_key_file_must_be_private_regular_file(tmp_path, kind):
    if os.name != "posix":
        pytest.skip("POSIX key file checks")
    path = tmp_path / "key"
    if kind == "public":
        path.touch(mode=0o644)
        path.write_bytes(KEY)
    elif kind == "symlink":
        target = tmp_path / "target"
        provision_key(target)
        path.symlink_to(target)
    elif kind == "directory":
        path.mkdir()
    else:
        os.mkfifo(path, 0o600)
    with pytest.raises(ValueError, match="private regular file"):
        AccountDigester.load(path)


def test_only_digests_reach_pins_audit_and_database_pages(tmp_path):
    store = GameAccountStore(tmp_path / "db", AccountDigester(KEY))
    assert admit(store) == "signed"
    for _ in range(2):
        with pytest.raises(AccountMismatch):
            admit(store, eos="abcdef0123456789abcdef0123456789")
    with sqlite3.connect(store.path) as db:
        pin = db.execute(
            "SELECT playfab_digest, steam_digest, eos_digest FROM user_accounts"
        ).fetchone()
        assert pin == store.identity_digests(PF.lower(), STEAM, EOS)
        assert all(type(value) is bytes and len(value) == 32 for value in pin)
        assert (
            db.execute("SELECT occurrence_count FROM validated_mismatches").fetchone()[
                0
            ]
            == 2
        )
    content = store.path.read_bytes()
    for raw in (PF, STEAM, EOS, "abcdef0123456789abcdef0123456789"):
        assert raw.encode() not in content
    assert KEY not in content


def test_wrong_key_or_format_never_resets_existing_pins(tmp_path):
    path = tmp_path / "db"
    store = GameAccountStore(path, AccountDigester(KEY))
    admit(store)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="key does not match"):
        GameAccountStore(path, AccountDigester(b"x" * 32))
    assert path.read_bytes() == before
    with sqlite3.connect(path) as db:
        db.execute("UPDATE account_settings SET identity_format='future-format'")
    with pytest.raises(ValueError, match="format or key"):
        GameAccountStore(path, AccountDigester(KEY))


def plaintext(path):
    path.touch(mode=0o600)
    limits = json.dumps(
        {"accounts": 100000, "mismatches": 100000, "database_pages": 16384},
        sort_keys=True,
    )
    ids = [str(uuid4()), str(uuid4())]
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE account_settings (id INTEGER PRIMARY KEY, limits_json TEXT NOT NULL)"
        )
        db.execute("INSERT INTO account_settings VALUES (1, ?)", (limits,))
        db.execute(
            "CREATE TABLE user_accounts (id TEXT PRIMARY KEY, playfab_id TEXT NOT NULL UNIQUE, steam_id TEXT UNIQUE, eos_id TEXT NOT NULL UNIQUE, first_login_date INTEGER NOT NULL, last_login_date INTEGER NOT NULL)"
        )
        db.execute(
            "CREATE TABLE validated_mismatches (id TEXT PRIMARY KEY, playfab_id TEXT NOT NULL, steam_id TEXT, eos_id TEXT NOT NULL, reason TEXT NOT NULL, first_mismatch_date INTEGER NOT NULL, last_mismatch_date INTEGER NOT NULL, occurrence_count INTEGER NOT NULL)"
        )
        db.execute(
            "INSERT INTO user_accounts VALUES (?, ?, ?, ?, 100, 200)",
            (ids[0], PF, STEAM, EOS),
        )
        db.execute(
            "INSERT INTO validated_mismatches VALUES (?, ?, NULL, ?, 'identity_conflict', 110, 210, 3)",
            (ids[1], PF, "abcdef0123456789abcdef0123456789"),
        )
    return ids


def test_plaintext_database_requires_explicit_migration(tmp_path):
    path = tmp_path / "legacy"
    plaintext(path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="explicit offline migration"):
        GameAccountStore(path, AccountDigester(KEY))
    assert path.read_bytes() == before


def test_offline_migration_preserves_ids_dates_counts_and_conflict_guarantees(tmp_path):
    source, target = tmp_path / "legacy", tmp_path / "digests"
    ids = plaintext(source)
    before = source.read_bytes()
    digester = AccountDigester(KEY)
    migrate_plaintext(source, target, digester)
    assert source.read_bytes() == before
    store = GameAccountStore(target, digester)
    with sqlite3.connect(target) as db:
        assert db.execute(
            "SELECT id, first_login_date, last_login_date FROM user_accounts"
        ).fetchone() == (ids[0], 100, 200)
        assert db.execute(
            "SELECT id, first_mismatch_date, last_mismatch_date, occurrence_count FROM validated_mismatches"
        ).fetchone() == (ids[1], 110, 210, 3)
    assert admit(store) == "signed"
    with pytest.raises(AccountMismatch):
        admit(store, eos="abcdef0123456789abcdef0123456789", steam=None)
    with sqlite3.connect(target) as db:
        assert (
            db.execute("SELECT occurrence_count FROM validated_mismatches").fetchone()[
                0
            ]
            == 4
        )
    for raw in (PF, STEAM, EOS):
        assert raw.encode() not in target.read_bytes()
    assert list(tmp_path.glob(".account-migration-*")) == []


def test_migration_never_overwrites_existing_destination(tmp_path):
    source, target = tmp_path / "legacy", tmp_path / "destination"
    plaintext(source)
    target.write_text("existing-work")
    with pytest.raises(FileExistsError):
        migrate_plaintext(source, target, AccountDigester(KEY))
    assert target.read_text() == "existing-work"


def test_invalid_source_never_publishes_partial_migration(tmp_path):
    source, target = tmp_path / "legacy", tmp_path / "digests"
    plaintext(source)
    with sqlite3.connect(source) as db:
        db.execute("UPDATE validated_mismatches SET reason='untrusted-text'")
    with pytest.raises(ValueError, match="Unsupported mismatch reason"):
        migrate_plaintext(source, target, AccountDigester(KEY))
    assert not target.exists()
    assert list(tmp_path.glob(".account-migration-*")) == []


def test_missing_tables_never_silently_recreate_a_pin_store(tmp_path):
    path = tmp_path / "db"
    GameAccountStore(path, AccountDigester(KEY))
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE user_accounts")
    with pytest.raises(ValueError, match="Incomplete account schema"):
        GameAccountStore(path, AccountDigester(KEY))


def test_missing_key_binding_never_adopts_a_replacement_key(tmp_path):
    path = tmp_path / "db"
    store = GameAccountStore(path, AccountDigester(KEY))
    admit(store)
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM account_settings")
    with pytest.raises(ValueError, match="Missing account key binding"):
        GameAccountStore(path, AccountDigester(b"x" * 32))
