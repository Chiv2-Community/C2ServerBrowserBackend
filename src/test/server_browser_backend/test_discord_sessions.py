"""Transactional quotas, opaque refresh rotation, and failure/restart behavior."""

import sqlite3
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

import pytest

from server_browser_backend.auth import sessions
from server_browser_backend.auth.sessions import (
    InvalidCredential,
    RefreshReplay,
    RefreshTooSoon,
    SessionBusy,
    SessionCapacity,
    SessionLimits,
    SessionStore,
)

ACCOUNT = "123456789012345678"
OTHER = "223456789012345678"


@pytest.fixture
def clock(monkeypatch):
    now = [1_800_000_000]
    monkeypatch.setattr(sessions.time, "time", lambda: now[0])
    return now


@pytest.fixture
def limits():
    return SessionLimits(
        sessions=4,
        per_account=2,
        credentials=12,
        per_session_credentials=3,
        idle_seconds=100,
        absolute_seconds=300,
        rotation_seconds=10,
        cleanup_batch=1,
    )


@pytest.fixture
def store(tmp_path, limits):
    return SessionStore(tmp_path / "sessions.sqlite3", limits)


def counts(store):
    with sqlite3.connect(store.path) as database:
        return tuple(
            database.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("sessions", "credentials")
        )


def test_restart_reuses_session_without_storing_raw_credentials(store, clock):
    created = store.create(ACCOUNT, clock[0] - 30)
    restored = SessionStore(store.path, store.limits)
    assert restored.authenticate(created.credential) == created.identity
    assert created.credential not in repr(created)
    assert created.credential.encode() not in store.path.read_bytes()
    assert counts(store) == (1, 1)
    assert store.path.stat().st_mode & 0o777 == 0o600


def test_rotation_preserves_auth_time_and_replay_revokes_descendants_only(store, clock):
    first = store.create(ACCOUNT, clock[0] - 30)
    unrelated = store.create(OTHER, clock[0] - 30)
    clock[0] += 10
    second = store.refresh(first.credential)
    assert second.credential != first.credential
    assert second.identity.auth_time == first.identity.auth_time
    assert second.identity.absolute_expires_at == first.identity.absolute_expires_at
    assert second.identity.expires_at > first.identity.expires_at
    with pytest.raises(RefreshReplay):
        store.refresh(first.credential)
    with pytest.raises(InvalidCredential):
        store.authenticate(second.credential)
    assert store.authenticate(unrelated.credential).discord_id == OTHER
    assert counts(store) == (1, 1)


def test_spent_credential_cannot_be_used_for_ticket_authentication(store, clock):
    first = store.create(ACCOUNT, clock[0])
    clock[0] += 10
    second = store.refresh(first.credential)
    with pytest.raises(RefreshReplay):
        store.authenticate(first.credential)
    with pytest.raises(InvalidCredential):
        store.refresh(second.credential)


def test_minimum_interval_rejects_without_rotating_or_revoking(store, clock):
    created = store.create(ACCOUNT, clock[0])
    clock[0] += 3
    with pytest.raises(RefreshTooSoon) as error:
        store.refresh(created.credential)
    assert error.value.retry_after == 7
    assert counts(store) == (1, 1)
    assert (
        store.authenticate(created.credential).session_id == created.identity.session_id
    )
    clock[0] += 7
    store.refresh(created.credential)


def test_absolute_lifetime_never_extends_and_idle_boundary_expires(store, clock):
    created = store.create(ACCOUNT, clock[0])
    for _ in range(3):
        clock[0] += 90
        identity = store.authenticate(created.credential)
        assert identity.absolute_expires_at == created.identity.absolute_expires_at
    assert identity.expires_at == created.identity.absolute_expires_at
    clock[0] += 30
    with pytest.raises(InvalidCredential):
        store.authenticate(created.credential)
    assert counts(store) == (0, 0)
    fresh = store.create(ACCOUNT, clock[0])
    clock[0] += 100
    with pytest.raises(InvalidCredential):
        store.authenticate(fresh.credential)


def test_full_account_and_global_quotas_never_evict_valid_sessions(store, clock):
    active = [store.create(ACCOUNT, clock[0]) for _ in range(2)]
    with pytest.raises(SessionCapacity):
        store.create(ACCOUNT, clock[0])
    active += [store.create(OTHER, clock[0]) for _ in range(2)]
    with pytest.raises(SessionCapacity):
        store.create("323456789012345678", clock[0])
    assert counts(store) == (4, 4)
    for session in active:
        store.authenticate(session.credential)


def test_history_limit_keeps_every_spent_hash_and_current_token_valid(store, clock):
    credential = store.create(ACCOUNT, clock[0]).credential
    initial = credential
    for _ in range(2):
        clock[0] += 10
        credential = store.refresh(credential).credential
    clock[0] += 10
    with pytest.raises(SessionCapacity, match="rotation budget"):
        store.refresh(credential)
    assert counts(store) == (1, 3)
    store.authenticate(credential)
    with pytest.raises(RefreshReplay):
        store.refresh(initial)
    assert counts(store) == (0, 0)


def test_global_credential_quota_is_transactional(tmp_path, limits, clock):
    limits = replace(limits, credentials=3)
    store = SessionStore(tmp_path / "small.sqlite3", limits)
    first = store.create(ACCOUNT, clock[0])
    second = store.create(OTHER, clock[0])
    clock[0] += 10
    rotated = store.refresh(first.credential)
    with pytest.raises(SessionCapacity, match="history budget"):
        store.refresh(second.credential)
    assert counts(store) == (2, 3)
    store.authenticate(second.credential)
    store.authenticate(rotated.credential)


def test_cleanup_is_bounded_and_cascades_hashes(store, clock):
    store.create(ACCOUNT, clock[0])
    store.create(OTHER, clock[0])
    clock[0] += 100
    assert store.cleanup() == 1
    assert counts(store) == (1, 1)
    assert store.cleanup() == 1
    assert counts(store) == (0, 0)


def test_cleanup_failure_rolls_back_and_preserves_valid_sessions(
    store, clock, monkeypatch
):
    created = store.create(ACCOUNT, clock[0])

    def fail(connection, now):
        connection.execute("DELETE FROM sessions")
        raise sqlite3.OperationalError("cleanup failure")

    with monkeypatch.context() as patched:
        patched.setattr(store, "_cleanup", fail)
        with pytest.raises(sqlite3.OperationalError, match="cleanup failure"):
            store.create(OTHER, clock[0])
    assert counts(store) == (1, 1)
    store.authenticate(created.credential)


@pytest.mark.parametrize("invalid", ["", "wrong", "x" * 44, "x" * 100000, "!" * 43])
def test_invalid_credentials_allocate_no_rows(store, invalid):
    for operation in (store.refresh, store.authenticate, store.logout):
        with pytest.raises(InvalidCredential):
            operation(invalid)
    assert counts(store) == (0, 0)


def test_logout_with_a_retained_hash_revokes_the_whole_family(store, clock):
    first = store.create(ACCOUNT, clock[0])
    clock[0] += 10
    second = store.refresh(first.credential)
    store.logout(first.credential)
    store.logout(first.credential)  # Idempotent.
    with pytest.raises(InvalidCredential):
        store.authenticate(second.credential)
    assert counts(store) == (0, 0)


def test_different_worker_limits_are_rejected_without_data_loss(store, clock):
    created = store.create(ACCOUNT, clock[0])
    with pytest.raises(ValueError, match="identical persisted limits"):
        SessionStore(store.path, replace(store.limits, sessions=5))
    store.authenticate(created.credential)


def test_busy_storage_leaves_credentials_usable(store, clock):
    created = store.create(ACCOUNT, clock[0])
    with sqlite3.connect(store.path, isolation_level=None) as locked:
        locked.execute("BEGIN IMMEDIATE")
        try:
            with pytest.raises(SessionBusy):
                store.authenticate(created.credential)
        finally:
            locked.rollback()
    assert (
        store.authenticate(created.credential).session_id == created.identity.session_id
    )


def after_sqlite_contention(store, clock, monkeypatch, now, operation):
    connect = sqlite3.connect
    contended = []
    with connect(store.path, isolation_level=None) as locked:
        locked.execute("BEGIN IMMEDIATE")

        class WaitingConnection(sqlite3.Connection):
            def execute(self, sql, parameters=()):
                try:
                    return super().execute(sql, parameters)
                except sqlite3.OperationalError as error:
                    if sql != "BEGIN IMMEDIATE" or error.sqlite_errorcode != sqlite3.SQLITE_BUSY:
                        raise
                    # A real failed lock acquisition advances the clock before retry.
                    contended.append(True)
                    clock[0] = now
                    locked.rollback()
                    return super().execute(sql, parameters)

        def waiting_connect(*args, **kwargs):
            return connect(*args, **{**kwargs, "timeout": 0, "factory": WaitingConnection})

        with monkeypatch.context() as patched:
            patched.setattr(sqlite3, "connect", waiting_connect)
            try:
                return operation()
            finally:
                locked.rollback()
                assert contended == [True]


@pytest.mark.parametrize("operation", ["authenticate", "refresh"])
@pytest.mark.parametrize("expiry", ["idle", "absolute"])
def test_lock_wait_crossing_expiry_rejects_credentials(
    store, clock, monkeypatch, operation, expiry
):
    created = store.create(ACCOUNT, clock[0])
    if expiry == "absolute":
        for _ in range(3):
            clock[0] += 90
            store.authenticate(created.credential)
        deadline = created.identity.absolute_expires_at
    else:
        deadline = created.identity.expires_at
    clock[0] = deadline - 1
    with pytest.raises(InvalidCredential):
        after_sqlite_contention(
            store, clock, monkeypatch, deadline,
            lambda: getattr(store, operation)(created.credential),
        )
    assert counts(store) == (0, 0)


def test_create_anchors_lifetimes_and_cleanup_after_lock_wait(store, clock, monkeypatch):
    old = store.create(ACCOUNT, clock[0])
    store.create(ACCOUNT, clock[0])
    auth_time = clock[0]
    now = old.identity.expires_at
    created = after_sqlite_contention(
        store, clock, monkeypatch, now, lambda: store.create(ACCOUNT, auth_time)
    )
    assert created.identity.auth_time == auth_time
    assert created.identity.expires_at == now + store.limits.idle_seconds
    assert created.identity.absolute_expires_at == now + store.limits.absolute_seconds
    with sqlite3.connect(store.path) as database:
        assert database.execute(
            "SELECT issued_at FROM credentials WHERE session_id=?",
            (created.identity.session_id,),
        ).fetchone()[0] == now


def test_insecure_or_nonregular_database_is_rejected(store):
    store.path.chmod(0o644)
    with pytest.raises(ValueError, match="group or other"):
        SessionStore(store.path, store.limits)
    with pytest.raises(ValueError, match="regular file"):
        SessionStore(store.path.parent, store.limits)


def create_in_worker(path, limits, now):
    try:
        return SessionStore(path, limits).create(ACCOUNT, now).credential
    except SessionCapacity:
        return None


def refresh_in_worker(path, limits, credential):
    try:
        return SessionStore(path, limits).refresh(credential).credential
    except RefreshReplay:
        return None


def test_concurrent_workers_enforce_the_same_account_quota(store):
    now = int(sessions.time.time())
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(create_in_worker, store.path, store.limits, now)
            for _ in range(4)
        ]
        credentials = [future.result(timeout=20) for future in futures]
    assert sum(credential is not None for credential in credentials) == 2
    assert counts(store) == (2, 2)


def test_concurrent_rotation_detects_reuse_and_revokes_the_winning_descendant(store):
    first = store.create(ACCOUNT, int(sessions.time.time()))
    # Advance only this row's age; child processes use their own real clocks.
    with sqlite3.connect(store.path) as database:
        database.execute("UPDATE credentials SET issued_at=issued_at-10")
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                refresh_in_worker, store.path, store.limits, first.credential
            )
            for _ in range(2)
        ]
        credentials = [future.result(timeout=20) for future in futures]
    assert sum(credential is not None for credential in credentials) == 1
    assert counts(store) == (0, 0)
    for credential in credentials:
        if credential is not None:
            with pytest.raises(InvalidCredential):
                store.authenticate(credential)


def test_disk_full_rolls_back_rotation_and_preserves_old_credential(store, clock):
    limited = SessionStore(
        store.path.parent / "full.sqlite3", replace(store.limits, database_pages=32)
    )
    active = limited.create(ACCOUNT, clock[0])
    with sqlite3.connect(limited.path) as database:
        database.execute("CREATE TABLE filler (payload BLOB)")
    # A deterministic trigger forces storage exhaustion during replacement,
    # exercising SQLite's actual FULL/rollback behavior, not a mocked insert.
    with sqlite3.connect(limited.path) as database:
        database.execute(
            "CREATE TRIGGER fill_on_rotation AFTER INSERT ON credentials BEGIN INSERT INTO filler VALUES (zeroblob(1000000)); END"
        )
    clock[0] += 10
    with pytest.raises(SessionCapacity):
        limited.refresh(active.credential)
    assert counts(limited) == (1, 1)
    limited.authenticate(active.credential)
    assert limited.path.stat().st_size <= 32 * 4096


@pytest.mark.parametrize(
    "field,value",
    [
        ("sessions", 0),
        ("credentials", -1),
        ("cleanup_batch", True),
        ("rotation_seconds", 100),
        ("idle_seconds", 301),
        ("per_account", 5),
        ("per_session_credentials", 13),
    ],
)
def test_invalid_limits_are_rejected(limits, field, value):
    with pytest.raises(ValueError):
        replace(limits, **{field: value})


@pytest.mark.parametrize(
    "identity,auth_time",
    [
        ("0", 1),
        ("000123", 1),
        ("not-discord", 1),
        (ACCOUNT, True),
        (ACCOUNT, 0),
        (ACCOUNT, 2**63),
    ],
)
def test_invalid_login_identity_allocates_no_rows(store, identity, auth_time):
    with pytest.raises(ValueError):
        store.create(identity, auth_time)
    assert counts(store) == (0, 0)
