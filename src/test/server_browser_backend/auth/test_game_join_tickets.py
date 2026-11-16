import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from server_browser_backend.auth.game_identity import VerifiedGameIdentity
from server_browser_backend.auth.game_join_tickets import (
    GameJoinCapacity,
    GameJoinLimits,
    GameJoinTicketStore,
    InvalidGameJoinTicket,
)

GENERATION = hashlib.sha256(b"server-registration-secret").digest()
IDENTITY = VerifiedGameIdentity("ABC123", "76561198000000000")


def test_valid_grant_is_single_use_and_raw_credential_is_not_stored(tmp_path):
    path = tmp_path / "tickets.db"
    store = GameJoinTicketStore(path)
    ticket = store.issue("server-a", GENERATION, IDENTITY)
    assert ticket.credential not in repr(ticket)
    assert ticket.credential.encode() not in path.read_bytes()
    assert store.redeem("server-a", GENERATION, ticket.credential, "abc123") == IDENTITY
    with pytest.raises(InvalidGameJoinTicket):
        store.redeem("server-a", GENERATION, ticket.credential, "ABC123")


@pytest.mark.parametrize(
    "server,generation,claim",
    [
        ("server-b", GENERATION, "ABC123"),
        ("server-a", b"x" * 32, "ABC123"),
        ("server-a", GENERATION, "DEF456"),
        ("server-a", GENERATION, "not-an-id"),
    ],
)
def test_failed_binding_checks_do_not_spend_the_ticket(
    tmp_path, server, generation, claim
):
    store = GameJoinTicketStore(tmp_path / "tickets.db")
    ticket = store.issue("server-a", GENERATION, IDENTITY)
    with pytest.raises(InvalidGameJoinTicket):
        store.redeem(server, generation, ticket.credential, claim)
    assert store.redeem("server-a", GENERATION, ticket.credential, "ABC123") == IDENTITY


@pytest.mark.parametrize(
    "credential", [None, "", "legacy-uuid-ticket", "x" * 43, "x" * 8192]
)
def test_unknown_and_legacy_tickets_are_rejected(tmp_path, credential):
    store = GameJoinTicketStore(tmp_path / "tickets.db")
    with pytest.raises(InvalidGameJoinTicket):
        store.redeem("server-a", GENERATION, credential, "ABC123")


def test_expiry_boundary_and_cleanup(tmp_path):
    now = [1000]
    store = GameJoinTicketStore(tmp_path / "tickets.db", clock=lambda: now[0])
    ticket = store.issue("server-a", GENERATION, IDENTITY)
    now[0] = ticket.expires_at
    with pytest.raises(InvalidGameJoinTicket):
        store.redeem("server-a", GENERATION, ticket.credential, "ABC123")
    assert store.issue("server-a", GENERATION, IDENTITY)


def test_two_workers_can_only_redeem_once(tmp_path):
    path = tmp_path / "tickets.db"
    stores = [GameJoinTicketStore(path), GameJoinTicketStore(path)]
    ticket = stores[0].issue("server-a", GENERATION, IDENTITY)

    def redeem(store):
        try:
            return store.redeem("server-a", GENERATION, ticket.credential, "ABC123")
        except InvalidGameJoinTicket:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(redeem, stores))
    assert results.count(IDENTITY) == 1
    assert results.count(None) == 1


def test_grants_survive_store_restart(tmp_path):
    path = tmp_path / "tickets.db"
    ticket = GameJoinTicketStore(path).issue("server-a", GENERATION, IDENTITY)
    assert (
        GameJoinTicketStore(path).redeem(
            "server-a", GENERATION, ticket.credential, "ABC123"
        )
        == IDENTITY
    )


def test_capacity_does_not_evict_live_grants(tmp_path):
    store = GameJoinTicketStore(
        tmp_path / "tickets.db", GameJoinLimits(tickets=2, per_account=1)
    )
    first = store.issue("server-a", GENERATION, IDENTITY)
    with pytest.raises(GameJoinCapacity):
        store.issue("server-a", GENERATION, IDENTITY)
    second_identity = VerifiedGameIdentity("DEF456")
    second = store.issue("server-a", GENERATION, second_identity)
    with pytest.raises(GameJoinCapacity):
        store.issue("server-a", GENERATION, VerifiedGameIdentity("AABB"))
    assert store.redeem("server-a", GENERATION, first.credential, "ABC123") == IDENTITY
    assert (
        store.redeem("server-a", GENERATION, second.credential, "DEF456")
        == second_identity
    )


def test_rejected_issuance_still_commits_bounded_cleanup(tmp_path):
    path = tmp_path / "tickets.db"
    now = [1000]
    limits = GameJoinLimits(tickets=4, per_account=1, cleanup_batch=1)
    store = GameJoinTicketStore(path, limits, clock=lambda: now[0])
    for identity in ["AA", "BB", "CC"]:
        store.issue("server-a", GENERATION, VerifiedGameIdentity(identity))
    now[0] = 1060
    live = store.issue("server-a", GENERATION, IDENTITY)
    with pytest.raises(GameJoinCapacity):
        store.issue("server-a", GENERATION, IDENTITY)
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute("SELECT count(*) FROM game_join_tickets").fetchone()[0]
            == 2
        )
    assert store.redeem("server-a", GENERATION, live.credential, "ABC123") == IDENTITY


def test_workers_must_share_limits(tmp_path):
    path = tmp_path / "tickets.db"
    GameJoinTicketStore(path)
    with pytest.raises(ValueError, match="identical"):
        GameJoinTicketStore(path, GameJoinLimits(tickets=16))


def test_storage_is_private_and_rejects_symlinks(tmp_path):
    path = tmp_path / "tickets.db"
    GameJoinTicketStore(path)
    assert path.stat().st_mode & 0o077 == 0
    link = tmp_path / "link.db"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="private regular"):
        GameJoinTicketStore(link)
