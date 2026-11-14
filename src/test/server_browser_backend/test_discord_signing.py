"""Persistent key/JWKS contracts; no OAuth/session service is exposed yet."""

import json
import fcntl
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import UUID

import jwt
import pytest
from fastapi.testclient import TestClient
from server_browser_models.models import JoinTicketClaims
from server_browser_models.runtime import contract

from server_browser_backend.auth import signing
from server_browser_backend.auth.signing import SigningKeys, provision

SERVER_ID = "18e532b1-6733-4b5a-9ffb-1cd7838bc7e4"
ISSUER = "https://servers.polehammer.net"


@pytest.fixture
def keys(tmp_path):
    path = tmp_path / "signing.json"
    provision(path)
    return SigningKeys(path)


def issue(keys):
    return keys.issue_join_ticket(
        issuer=ISSUER,
        discord_id="123456789012345678",
        server_id=SERVER_ID,
        auth_time=int(time.time()) - 10,
    )


def issue_in_worker(path):
    return issue(SigningKeys(path))


def test_join_timestamps_use_64_bit_generated_contracts(keys, monkeypatch):
    monkeypatch.setattr(signing.time, "time", lambda: 4_000_000_000)
    token = issue(keys)
    claims = jwt.decode(token, options={"verify_signature": False})
    assert JoinTicketClaims.from_json(claims).exp == 4_000_000_060
    properties = contract()["components"]["schemas"]["JoinTicketClaims"]["properties"]
    for name in ("auth_time", "iat", "nbf", "exp"):
        assert properties[name]["format"] == "int64"


def verify(keys, token):
    header = jwt.get_unverified_header(token)
    public = next(
        key
        for key in jwt.PyJWKSet.from_dict(keys.get_jwks_response().model_dump()).keys
        if key.key_id == header["kid"]
    )
    return jwt.decode(
        token,
        public.key,
        algorithms=["RS256"],
        issuer=ISSUER,
        audience=f"urn:unchained:server:{SERVER_ID}",
        options={
            "require": [
                "iss",
                "sub",
                "aud",
                "purpose",
                "auth_time",
                "iat",
                "nbf",
                "exp",
                "jti",
            ]
        },
    )


def test_restart_and_independent_workers_share_persistent_identity(keys):
    restarted = SigningKeys(keys.path)
    token = issue(keys)
    assert restarted.get_jwks_response() == keys.get_jwks_response()
    payload = verify(restarted, token)
    assert JoinTicketClaims.from_json(payload).purpose == "unchained.join"
    assert payload["sub"] == "123456789012345678"
    assert payload["exp"] - payload["iat"] == 60
    assert payload["nbf"] == payload["iat"]
    assert payload["auth_time"] < payload["iat"]
    assert str(UUID(payload["jti"])) == payload["jti"]
    assert verify(keys, issue(restarted))["jti"] != payload["jti"]
    assert jwt.get_unverified_header(token)["typ"] == "unchained-join+jwt"
    with pytest.raises(jwt.InvalidAudienceError):
        jwk = jwt.PyJWK.from_dict(keys.get_jwks_response().keys[0].model_dump())
        jwt.decode(
            token,
            jwk.key,
            algorithms=["RS256"],
            issuer=ISSUER,
            audience="another-server",
        )


def test_rotation_is_visible_to_existing_workers_and_retains_old_public_keys(
    keys, monkeypatch
):
    old_token = issue(keys)
    old_jwks = keys.get_jwks_response()
    provision(keys.path, rotate=True)
    new_token = issue(keys)
    assert (
        jwt.get_unverified_header(old_token)["kid"]
        != jwt.get_unverified_header(new_token)["kid"]
    )
    assert len(keys.get_jwks_response().keys) == 2
    verify(keys, old_token)
    verify(SigningKeys(keys.path), new_token)
    document = json.loads(keys.path.read_text())
    retired = next(
        entry for entry in document["keys"] if entry["kid"] != document["active_kid"]
    )
    assert set(retired) == {"kid", "public_key", "retire_after"}
    monkeypatch.setattr(signing.time, "time", lambda: retired["retire_after"])
    assert len(keys.get_jwks_response().keys) == 1
    assert keys.get_jwks_response().keys[0].kid != old_jwks.keys[0].kid


def test_rotation_capacity_never_discards_unexpired_keys(keys, monkeypatch):
    monkeypatch.setattr(signing, "MAX_KEYS", 2)
    provision(keys.path, rotate=True)
    before = keys.path.read_bytes()
    with pytest.raises(ValueError, match="capacity"):
        provision(keys.path, rotate=True)
    assert keys.path.read_bytes() == before
    assert len(keys.get_jwks_response().keys) == 2


def test_slow_rotation_retains_tickets_issued_during_generation(
    keys, monkeypatch, app_factory
):
    clock = [1_800_000_000]
    monkeypatch.setattr(signing.time, "time", lambda: clock[0])
    generate = signing.rsa.generate_private_key
    issued = []

    def slow_generation(**kwargs):
        clock[0] += 40
        issued.append(issue(keys))
        return generate(**kwargs)

    monkeypatch.setattr(signing.rsa, "generate_private_key", slow_generation)
    provision(keys.path, rotate=True)
    token = issued[0]
    old_kid = jwt.get_unverified_header(token)["kid"]
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["exp"] == 1_800_000_100
    retirement = claims["exp"] + signing.CLOCK_SKEW_SECONDS
    document = json.loads(keys.path.read_text())
    retired = next(entry for entry in document["keys"] if entry["kid"] == old_kid)
    assert retired["retire_after"] == retirement
    with TestClient(app_factory(signing_keys=keys)) as client:
        for now in (1_800_000_090, claims["exp"] - 1, retirement - 1):
            clock[0] = now
            response = client.get("/api/v1/auth/jwks.json")
            assert response.status_code == 200
            public = next(
                key for key in jwt.PyJWKSet.from_dict(response.json()).keys
                if key.key_id == old_kid
            )
            assert jwt.decode(
                token, public.key, algorithms=["RS256"], issuer=ISSUER,
                audience=f"urn:unchained:server:{SERVER_ID}",
                options={"verify_exp": False, "verify_iat": False, "verify_nbf": False},
            ) == claims
        clock[0] = retirement
        assert old_kid not in {
            key["kid"] for key in client.get("/api/v1/auth/jwks.json").json()["keys"]
        }


def test_failed_key_generation_preserves_old_keyring(keys, monkeypatch):
    before = keys.path.read_bytes()
    token = issue(keys)

    def fail(**kwargs):
        raise RuntimeError("generation failed")

    monkeypatch.setattr(signing.rsa, "generate_private_key", fail)
    with pytest.raises(RuntimeError, match="generation failed"):
        provision(keys.path, rotate=True)
    assert keys.path.read_bytes() == before
    assert not list(keys.path.parent.glob(".signing-*"))
    verify(keys, token)


def test_delayed_publication_blocks_issuance_and_refreshes_cached_key(keys, monkeypatch):
    clock = [1_800_000_000]
    monkeypatch.setattr(signing.time, "time", lambda: clock[0])
    old_token = issue(keys)  # Populate the worker snapshot before rotation.
    old_kid = jwt.get_unverified_header(old_token)["kid"]
    attempted = Event()
    flock = fcntl.flock
    fsync = signing.os.fsync
    futures = []

    def tracked_flock(descriptor, operation):
        if operation == fcntl.LOCK_SH:
            attempted.set()
        return flock(descriptor, operation)

    with ThreadPoolExecutor(max_workers=1) as executor:
        def delayed_fsync(descriptor):
            if not futures:
                futures.append(executor.submit(issue, keys))
                assert attempted.wait(5)
                assert not futures[0].done()
                # Longer than the full old-key retention window.
                clock[0] += 140
                # JWKS remains readable while publication holds the writer lock.
                assert keys.get_jwks_response().keys[0].kid == old_kid
            return fsync(descriptor)

        monkeypatch.setattr(fcntl, "flock", tracked_flock)
        monkeypatch.setattr(signing.os, "fsync", delayed_fsync)
        provision(keys.path, rotate=True)
        token = futures[0].result(timeout=5)
    assert jwt.get_unverified_header(token)["kid"] != old_kid
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["iat"] == clock[0]
    assert claims["exp"] == clock[0] + signing.TICKET_SECONDS
    document = json.loads(keys.path.read_text())
    retirement = next(e["retire_after"] for e in document["keys"] if e["kid"] == old_kid)
    old_claims = jwt.decode(old_token, options={"verify_signature": False})
    assert retirement >= old_claims["exp"] + signing.CLOCK_SKEW_SECONDS


def test_jwks_reads_do_not_require_a_writable_or_present_lock(keys, monkeypatch):
    expected = keys.get_jwks_response()
    Path(str(keys.path) + ".lock").unlink()

    def unexpected_lock(*args, **kwargs):
        raise AssertionError("public JWKS must not acquire a provisioning lock")

    monkeypatch.setattr(signing, "provisioning_lock", unexpected_lock)
    assert SigningKeys(keys.path).get_jwks_response() == expected


def test_rotation_waits_for_in_flight_old_key_issuance(keys, monkeypatch):
    clock = [1_800_000_000]
    monkeypatch.setattr(signing.time, "time", lambda: clock[0])
    encoding = Event()
    release = Event()
    rotating = Event()
    encode = jwt.encode
    flock = fcntl.flock

    def delayed_encode(*args, **kwargs):
        encoding.set()
        assert release.wait(5)
        return encode(*args, **kwargs)

    def tracked_flock(descriptor, operation):
        if operation == fcntl.LOCK_EX:
            rotating.set()
        return flock(descriptor, operation)

    monkeypatch.setattr(jwt, "encode", delayed_encode)
    monkeypatch.setattr(fcntl, "flock", tracked_flock)
    with ThreadPoolExecutor(max_workers=2) as executor:
        issued = executor.submit(issue, keys)
        try:
            assert encoding.wait(5)
            rotation = executor.submit(provision, keys.path, rotate=True)
            assert rotating.wait(5)
            assert not rotation.done()
            clock[0] += 40
        finally:
            release.set()
        token = issued.result(timeout=5)
        rotation.result(timeout=5)
    kid = jwt.get_unverified_header(token)["kid"]
    document = json.loads(keys.path.read_text())
    retired = next(e for e in document["keys"] if e["kid"] == kid)
    assert retired["retire_after"] == (
        clock[0] + signing.TICKET_SECONDS + signing.CLOCK_SKEW_SECONDS
    )


def test_failed_publication_fsync_preserves_old_keyring(keys, monkeypatch):
    before = keys.path.read_bytes()

    def fail(descriptor):
        raise OSError("fsync failure")

    monkeypatch.setattr(signing.os, "fsync", fail)
    with pytest.raises(OSError, match="fsync failure"):
        provision(keys.path, rotate=True)
    assert keys.path.read_bytes() == before
    assert not list(keys.path.parent.glob(".signing-*"))
    verify(keys, issue(keys))


def test_jwks_reuses_one_snapshot_and_revalidates_changed_configuration(
    keys, monkeypatch
):
    def unexpected_read():
        raise AssertionError("unchanged keyring was parsed again")

    with monkeypatch.context() as patched:
        patched.setattr(keys, "_read", unexpected_read)
        keys.get_jwks_response()
        keys.get_jwks_response()
    keys.path.write_text("invalid secret-sentinel")
    with pytest.raises(ValueError, match="^Invalid signing keyring$"):
        keys.get_jwks_response()


def test_retired_key_cleanup_restores_rotation_capacity(keys, monkeypatch):
    monkeypatch.setattr(signing, "MAX_KEYS", 2)
    provision(keys.path, rotate=True)
    retired = next(
        entry
        for entry in json.loads(keys.path.read_text())["keys"]
        if "retire_after" in entry
    )
    monkeypatch.setattr(signing.time, "time", lambda: retired["retire_after"])
    provision(keys.path, rotate=True)
    assert len(keys.get_jwks_response().keys) == 2


def test_concurrent_rotations_serialize_without_losing_verification_keys(keys):
    token = issue(keys)
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(provision, keys.path, rotate=True) for _ in range(2)]
        for future in futures:
            future.result(timeout=20)
    assert len(keys.get_jwks_response().keys) == 3
    verify(keys, token)


def test_separate_worker_processes_issue_against_the_same_jwks(keys):
    with ProcessPoolExecutor(max_workers=2) as executor:
        tokens = list(executor.map(issue_in_worker, [keys.path, keys.path]))
    assert len({verify(keys, token)["jti"] for token in tokens}) == 2
    assert len({jwt.get_unverified_header(token)["kid"] for token in tokens}) == 1


def test_provisioning_refuses_overwrite_and_uses_private_permissions(keys):
    before = keys.path.read_bytes()
    with pytest.raises(FileExistsError):
        provision(keys.path)
    assert keys.path.read_bytes() == before
    assert keys.path.stat().st_mode & 0o777 == 0o600
    keys.path.chmod(0o644)
    with pytest.raises(ValueError, match="group or other"):
        SigningKeys(keys.path)


def test_failed_atomic_replace_preserves_old_keyring(keys, monkeypatch):
    before = keys.path.read_bytes()

    def fail(*args):
        raise OSError("disk failure")

    monkeypatch.setattr(signing.os, "replace", fail)
    with pytest.raises(OSError, match="disk failure"):
        provision(keys.path, rotate=True)
    assert keys.path.read_bytes() == before
    assert not list(keys.path.parent.glob(".signing-*"))


@pytest.mark.parametrize(
    "document",
    [
        {},
        [],
        None,
        {"active_kid": "missing", "keys": []},
        {
            "active_kid": "secret-sentinel",
            "keys": [{"kid": "secret-sentinel", "private_key": "secret-sentinel"}],
        },
    ],
)
def test_invalid_keyring_is_rejected_without_disclosing_secrets(tmp_path, document):
    path = tmp_path / "signing.json"
    path.write_text(json.dumps(document))
    path.chmod(0o600)
    with pytest.raises(ValueError, match="^Invalid signing keyring$") as error:
        SigningKeys(path)
    assert "secret-sentinel" not in str(error.value)


def test_oversized_and_missing_keyrings_fail_explicitly(tmp_path):
    path = tmp_path / "signing.json"
    with pytest.raises(FileNotFoundError):
        SigningKeys(path)
    path.write_bytes(b"x" * (signing.MAX_KEYRING_BYTES + 1))
    path.chmod(0o600)
    with pytest.raises(ValueError, match="size limit"):
        SigningKeys(path)
    with pytest.raises(ValueError, match="regular file"):
        SigningKeys(tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("issuer", "http://issuer.test"),
        ("issuer", "https://user:secret@issuer.test"),
        ("issuer", "https://issuer.test?key=secret"),
        ("discord_id", "0"),
        ("discord_id", "000123"),
        ("discord_id", str(2**64)),
        ("discord_id", "١٢٣"),
        ("server_id", "not-a-registration"),
        ("auth_time", True),
        ("auth_time", 0),
        ("auth_time", int(time.time()) + 3600),
    ],
)
def test_invalid_claim_inputs_are_rejected(keys, field, value):
    inputs = dict(
        issuer=ISSUER,
        discord_id="123456789012345678",
        server_id=SERVER_ID,
        auth_time=int(time.time()) - 1,
    )
    inputs[field] = value
    with pytest.raises(ValueError):
        keys.issue_join_ticket(**inputs)


def test_jwks_api_publishes_only_public_material_and_eos_exchange_is_retired(
    app_factory, keys, caplog
):
    app = app_factory(signing_keys=keys)
    with TestClient(app) as client:
        response = client.get("/api/v1/auth/jwks.json")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert set(response.json()["keys"][0]) == {"kty", "alg", "use", "kid", "n", "e"}
        retired = client.post(
            "/api/v1/auth/login", json={"token": "secret-eos-sentinel"}
        )
        assert retired.status_code == 410
        assert retired.json()["status"] == "auth_retired"
    assert "PRIVATE" not in response.text
    assert "secret-eos-sentinel" not in caplog.text


def test_unconfigured_signing_publishes_no_ephemeral_key(app):
    assert app.browser_api.signing_keys is None
    with TestClient(app) as client:
        assert client.get("/api/v1/auth/jwks.json").json() == {"keys": []}


def test_configured_missing_keyring_fails_production_startup(tmp_path):
    environment = {
        **os.environ,
        "CONFIG_DIR": str(tmp_path),
        "DISCORD_SIGNING_KEYRING": str(tmp_path / "missing.json"),
    }
    process = subprocess.run(
        [sys.executable, "-c", "import server_browser_backend.main"],
        env=environment,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert process.returncode != 0
    assert "FileNotFoundError" in process.stderr
