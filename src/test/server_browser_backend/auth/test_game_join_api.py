import hashlib
from dataclasses import replace
from datetime import datetime
from ipaddress import ip_address
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from server_browser_backend.auth.game_identity import (
    GameIdentityUnavailable,
    InvalidGameCredential,
    PlayFabIdentityVerifier,
    VerifiedGameIdentity,
)
from server_browser_backend.auth.game_join import GameJoinService
from server_browser_backend.auth.game_join_tickets import GameJoinTicketStore


@pytest.fixture
def joining(app, browser, tmp_path):
    verifier = Mock(spec=PlayFabIdentityVerifier)
    verifier.verify.return_value = VerifiedGameIdentity("ABC123")
    browser.game_join = GameJoinService(
        browser.server_list,
        verifier,
        GameJoinTicketStore(tmp_path / "tickets.sqlite"),
        "https://browser.example",
    )
    with TestClient(app, client=("198.51.100.1", 12345)) as client:
        registration = client.post(
            "/api/v1/servers",
            json={
                "ports": {"game": 7777, "a2s": 7778, "ping": 7779},
                "name": "test",
                "description": "",
                "current_map": "map",
                "player_count": 0,
                "max_players": 32,
            },
        ).json()
        server_id = registration["server"]["unique_id"]
        yield client, browser.game_join, verifier, server_id, registration["key"]


SECRET = "s" * 43


@pytest.fixture
def signed_joining(joining, browser, tmp_path):
    import time

    from server_browser_backend.auth.account_digests import AccountDigester
    from server_browser_backend.auth.eos_identity import (
        EosConnectVerifier,
        VerifiedEosIdentity,
    )
    from server_browser_backend.auth.game_accounts import GameAccountStore
    from server_browser_backend.auth.signing import SigningKeys, provision

    client, service, verifier, server, key = joining
    path = tmp_path / "game-signing.json"
    provision(path)
    service.signing = SigningKeys(path)
    service.accounts = GameAccountStore(
        tmp_path / "accounts.sqlite", AccountDigester(b"k" * 32)
    )
    verifier.verify_steam_link.side_effect = (
        lambda identity, steam: VerifiedGameIdentity(identity.playfab_id, steam)
    )
    browser.game_signing_keys = service.signing
    service.eos = Mock(spec=EosConnectVerifier)
    service.eos.verify.return_value = VerifiedEosIdentity(
        "a" * 32, "steam", "76561198000000001", int(time.time()) + 300
    )
    service.tickets = None
    return joining


def admission(client, challenge):
    return client.post(
        "/api/v1/game-admissions",
        json={
            "challenge_id": challenge,
            "secret": SECRET,
            "eos_id_token": "synthetic-proof",
        },
    )


def test_signed_admission_contains_only_verified_claims(signed_joining, caplog):
    import time

    import jwt

    client, service, verifier, server, key = signed_joining
    challenge = begin(client).json()["challenge_id"]
    response = admission(client, challenge)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    token = response.json()["ticket"]
    header = jwt.get_unverified_header(token)
    jwks = client.get("/api/v1/game-join-jwks.json")
    assert jwks.headers["cache-control"] == "no-store"
    public = next(
        key
        for key in jwt.PyJWKSet.from_dict(jwks.json()).keys
        if key.key_id == header["kid"]
    )
    claims = jwt.decode(
        token,
        public.key,
        algorithms=["RS256"],
        issuer="https://browser.example",
        audience=f"urn:unchained:server:{server}",
    )
    assert header["typ"] == "unchained-game-join+jwt"
    assert claims["purpose"] == "unchained.game-join" and claims["version"] == 1
    assert claims["sub"] == "ABC123"
    assert claims["identities"] == {
        "playfab": "ABC123",
        "eos_product_user_id": "a" * 32,
        "platform": {"provider": "steam", "id": "76561198000000001"},
    }
    assert claims["iat"] == claims["nbf"]
    assert 0 < claims["exp"] - claims["iat"] <= 60
    assert response.json()["expires_at"] == claims["exp"]
    assert claims["exp"] > int(time.time())
    assert admission(client, challenge).status_code == 401
    assert token not in caplog.text and "synthetic-proof" not in caplog.text
    service.eos.verify.assert_called_once_with("synthetic-proof")
    verifier.verify.assert_called_once()
    assert redeem(client, server, key, "a" * 43).status_code == 503
    assert issue(client).status_code == 503


@pytest.mark.parametrize("provider", ["eos", "playfab"])
@pytest.mark.parametrize(
    "failure,expected", [(InvalidGameCredential, 401), (GameIdentityUnavailable, 503)]
)
def test_signed_admission_rejects_either_invalid_proof(
    signed_joining, provider, failure, expected
):
    client, service, verifier, _, _ = signed_joining
    (service.eos if provider == "eos" else verifier).verify.side_effect = failure()
    challenge = begin(client).json()["challenge_id"]
    assert admission(client, challenge).status_code == expected


def test_signed_admission_rechecks_registration_after_provider_io(signed_joining):
    client, service, verifier, server, key = signed_joining
    challenge = begin(client).json()["challenge_id"]
    verifier.verify.side_effect = lambda *_: (
        service.registry.delete(server, key),
        VerifiedGameIdentity("ABC123"),
    )[1]
    assert admission(client, challenge).status_code == 404


def test_signed_admission_cannot_outlive_eos_proof(signed_joining):
    import time
    from dataclasses import replace

    import jwt

    client, service, _, _, _ = signed_joining
    expires = int(time.time()) + 10
    service.eos.verify.return_value = replace(
        service.eos.verify.return_value, expires_at=expires
    )
    result = admission(client, begin(client).json()["challenge_id"])
    assert result.status_code == 200
    assert (
        jwt.decode(result.json()["ticket"], options={"verify_signature": False})["exp"]
        == expires
    )


def test_signed_admission_rejects_proof_expiring_during_playfab_read(signed_joining):
    import time
    from dataclasses import replace

    client, service, verifier, _, _ = signed_joining
    service.eos.verify.return_value = replace(
        service.eos.verify.return_value, expires_at=int(time.time()) - 1
    )
    assert admission(client, begin(client).json()["challenge_id"]).status_code == 401


def account_rows(service, table):
    import sqlite3

    with sqlite3.connect(service.accounts.path) as db:
        return db.execute(f"SELECT * FROM {table}").fetchall()


def test_signed_admission_pins_and_audits_verified_conflict(signed_joining):
    client, service, _, _, _ = signed_joining
    assert admission(client, begin(client).json()["challenge_id"]).status_code == 200
    original = account_rows(service, "user_accounts")
    service.eos.verify.return_value = replace(
        service.eos.verify.return_value, product_user_id="b" * 32
    )
    service.signing = Mock(wraps=service.signing)
    for _ in range(2):
        challenge = begin(client).json()["challenge_id"]
        response = admission(client, challenge)
        assert response.status_code == 409
        assert response.json() == {
            "status": "account_mismatch",
            "message": "Account Mismatch",
            "context": None,
        }
        assert response.headers["cache-control"] == "no-store"
        assert admission(client, challenge).status_code == 401
    assert account_rows(service, "user_accounts") == original
    assert len(account_rows(service, "validated_mismatches")) == 1
    assert account_rows(service, "validated_mismatches")[0][-1] == 2
    service.signing.issue_game_admission.assert_not_called()


@pytest.mark.parametrize("provider", ["eos", "playfab", "steam_link"])
def test_invalid_proofs_never_create_pins_or_mismatch_audit(signed_joining, provider):
    client, service, verifier, _, _ = signed_joining
    if provider == "steam_link":
        verifier.verify_steam_link.side_effect = InvalidGameCredential()
    else:
        (service.eos if provider == "eos" else verifier).verify.side_effect = (
            InvalidGameCredential()
        )
    assert admission(client, begin(client).json()["challenge_id"]).status_code == 401
    assert account_rows(service, "user_accounts") == []
    assert account_rows(service, "validated_mismatches") == []


def test_registration_removed_during_steam_lookup_cannot_pin(signed_joining):
    client, service, verifier, server, key = signed_joining

    def lookup(identity, steam):
        service.registry.delete(server, key)
        return VerifiedGameIdentity(identity.playfab_id, steam)

    verifier.verify_steam_link.side_effect = lookup
    assert admission(client, begin(client).json()["challenge_id"]).status_code == 404
    assert account_rows(service, "user_accounts") == []


def test_signed_admission_requires_durable_account_storage(signed_joining):
    client, service, _, _, _ = signed_joining
    service.accounts = None
    assert admission(client, begin(client).json()["challenge_id"]).status_code == 503


def test_epic_pinning_does_not_require_steam_or_claim_provider_linkage(signed_joining):
    client, service, verifier, _, _ = signed_joining
    service.eos.verify.return_value = replace(
        service.eos.verify.return_value, platform_provider="eos", platform_id="a" * 32
    )
    assert admission(client, begin(client).json()["challenge_id"]).status_code == 200
    verifier.verify_steam_link.assert_not_called()
    assert account_rows(service, "user_accounts")[0][2] is None
    service.eos.verify.return_value = replace(
        service.eos.verify.return_value, product_user_id="b" * 32, platform_id="b" * 32
    )
    assert admission(client, begin(client).json()["challenge_id"]).status_code == 409


def begin(client, **changes):
    return client.post(
        "/api/v1/game-join-challenges",
        json={
            "playfab_id": "ABC123",
            "commitment": hashlib.sha256(SECRET.encode()).hexdigest(),
            "audience": "https://browser.example",
            "target_ip": "198.51.100.1",
            "target_port": 7777,
            **changes,
        },
    )


def issue(client, **changes):
    challenge = begin(client, **changes)
    if challenge.status_code != 200:
        return challenge
    return client.post(
        "/api/v1/game-join-tickets",
        json={"challenge_id": challenge.json()["challenge_id"], "secret": SECRET},
    )


def redeem(client, server_id, key, ticket, playfab_id="ABC123"):
    return client.post(
        f"/api/v1/servers/{server_id}/game-join-tickets/redeem",
        headers={"X-CHIV2-SERVER-BROWSER-KEY": key},
        json={"ticket": ticket, "playfab_id": playfab_id},
    )


def test_single_use_and_verified_account(joining, caplog):
    client, service, verifier, server_id, key = joining
    grant = issue(client)
    assert grant.status_code == 200
    assert grant.headers["cache-control"] == "no-store"
    assert grant.json()["server_id"] == server_id
    assert "secret" not in caplog.text
    assert verifier.verify.call_args.args[0] == "ABC123"
    assert verifier.verify.call_args.args[1].startswith("uc-proof-v1:")
    ticket = grant.json()["ticket"]
    assert redeem(client, server_id, key, ticket, "DEF").status_code == 403
    assert redeem(client, server_id, "wrong", ticket).status_code == 403
    accepted = redeem(client, server_id, key, ticket)
    assert accepted.status_code == 200
    assert accepted.json() == {"playfab_id": "ABC123"}
    assert accepted.headers["cache-control"] == "no-store"
    assert redeem(client, server_id, key, ticket).status_code == 403
    assert ticket not in caplog.text


@pytest.mark.parametrize(
    "failure, expected", [(InvalidGameCredential, 401), (GameIdentityUnavailable, 503)]
)
def test_verification_fails_closed(joining, failure, expected):
    client, service, verifier, server_id, key = joining
    verifier.verify.side_effect = failure()
    assert issue(client).status_code == expected


def test_unknown_and_ambiguous_targets_skip_verification(joining):
    client, service, verifier, server_id, key = joining
    assert issue(client, target_port=7776).status_code == 404
    original = service.registry.get(server_id)
    service.registry.register(replace(original, unique_id="duplicate"))
    assert issue(client).status_code == 404
    verifier.verify.assert_not_called()


@pytest.mark.parametrize(
    "change", ["expired", "deleted", "generation", "source", "ticket_expired"]
)
def test_invalidated_registration_or_ticket(joining, change):
    client, service, verifier, server_id, key = joining
    ticket = issue(client).json()["ticket"]
    if change == "expired":
        service.registry.update(
            server_id, key, lambda server: replace(server, last_heartbeat=0)
        )
    elif change == "deleted":
        service.registry.delete(server_id, key)
    elif change == "generation":
        server = service.registry.delete(server_id, key)
        key = service.registry.register(server)
    elif change == "source":
        service.registry.update(
            server_id,
            key,
            lambda server: replace(server, ip_address=ip_address("198.51.100.2")),
        )
    else:
        service.tickets.clock = lambda: datetime.now().timestamp() + 120
    assert redeem(client, server_id, key, ticket).status_code == 403


def test_bounded_verification_budget(joining):
    client, service, verifier, server_id, key = joining
    verifier.verify.side_effect = InvalidGameCredential()
    challenge = begin(client).json()["challenge_id"]
    for _ in range(12):
        assert (
            client.post(
                "/api/v1/game-join-tickets",
                json={"challenge_id": challenge, "secret": SECRET},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/v1/game-join-tickets",
            json={"challenge_id": challenge, "secret": SECRET},
        ).status_code
        == 429
    )
    assert verifier.verify.call_count == 12


def test_public_commitment_is_not_a_completion_secret(joining):
    client, service, verifier, _, _ = joining
    challenge = begin(client).json()
    response = client.post(
        "/api/v1/game-join-tickets",
        json={"challenge_id": challenge["challenge_id"], "secret": "a" * 43},
    )
    assert response.status_code == 401
    verifier.verify.assert_not_called()
    assert "proof" not in challenge and "secret" not in challenge


def test_challenge_completion_replay_is_rejected(joining):
    client, _, verifier, _, _ = joining
    challenge = begin(client).json()["challenge_id"]
    body = {"challenge_id": challenge, "secret": SECRET}
    assert client.post("/api/v1/game-join-tickets", json=body).status_code == 200
    assert client.post("/api/v1/game-join-tickets", json=body).status_code == 401
    assert verifier.verify.call_count == 1


def test_audience_and_legacy_bearer_requests_are_rejected(joining):
    client, _, verifier, _, _ = joining
    assert begin(client, audience="https://other.example").status_code == 401
    assert (
        client.post(
            "/api/v1/game-join-tickets",
            json={
                "credential": "player-bearer",
                "target_ip": "198.51.100.1",
                "target_port": 7777,
            },
        ).status_code
        == 400
    )
    verifier.verify.assert_not_called()


def test_completion_rejects_extra_player_credential_field(joining):
    client, _, verifier, _, _ = joining
    challenge = begin(client).json()["challenge_id"]
    assert (
        client.post(
            "/api/v1/game-join-tickets",
            json={
                "challenge_id": challenge,
                "secret": SECRET,
                "credential": "synthetic-not-a-session",
            },
        ).status_code
        == 400
    )
    verifier.verify.assert_not_called()


def test_public_proof_matches_rust_vector():
    from server_browser_backend.auth.game_join import account_proof

    assert (
        account_proof(
            "https://browser.example", "server-1", "ABC123", "c" * 43, "d" * 64
        )
        == "uc-proof-v1:6205faeb8b646982ebe2fbc7aaa3c6e34d7ed72f03222965824407f5342557d8"
    )


@pytest.mark.parametrize(
    "mutation", ["expiry", "source", "generation", "identity", "expiry_during_read"]
)
def test_challenge_binding_survives_network_io(joining, mutation):
    client, service, verifier, server, key = joining
    challenge = begin(client).json()["challenge_id"]
    if mutation == "expiry":
        service.clock = lambda: datetime.now().timestamp() + 120
    elif mutation == "source":
        from server_browser_backend.auth.game_identity import InvalidGameCredential

        with pytest.raises(InvalidGameCredential):
            service.issue("198.51.100.2", challenge, SECRET)
        verifier.verify.assert_not_called()
        return
    elif mutation == "generation":
        current = service.registry.delete(server, key)
        service.registry.register(current)
    elif mutation == "identity":
        verifier.verify.return_value = VerifiedGameIdentity("DEF")
    else:

        def expire(*_):
            service.clock = lambda: datetime.now().timestamp() + 120
            return VerifiedGameIdentity("ABC123")

        verifier.verify.side_effect = expire
    assert client.post(
        "/api/v1/game-join-tickets", json={"challenge_id": challenge, "secret": SECRET}
    ).status_code in (401, 404)


def test_pending_challenges_are_bounded_per_source_not_claimed_account(joining):
    client, _, verifier, _, _ = joining
    for _ in range(12):
        assert begin(client).status_code == 200
    assert begin(client).status_code == 429
    verifier.verify.assert_not_called()


def test_claimed_account_cannot_reserve_victims_challenge_budget(joining):
    client, service, _, _, _ = joining
    for _ in range(4):
        assert begin(client).status_code == 200
    assert (
        service.begin(
            "198.51.100.2",
            ip_address("198.51.100.1"),
            7777,
            "ABC123",
            hashlib.sha256(SECRET.encode()).hexdigest(),
            "https://browser.example",
        ).playfab_id
        == "ABC123"
    )


def test_concurrent_completion_mints_one_grant(joining):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    client, service, verifier, _, _ = joining
    challenge = begin(client).json()["challenge_id"]
    barrier = threading.Barrier(2)

    def verify(*_):
        barrier.wait(timeout=5)
        return VerifiedGameIdentity("ABC123")

    verifier.verify.side_effect = verify

    def complete():
        try:
            service.issue("198.51.100.1", challenge, SECRET)
            return True
        except InvalidGameCredential:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: complete(), range(2))) == [False, True]
