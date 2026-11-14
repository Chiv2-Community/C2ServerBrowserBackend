"""Persistent key/JWKS contracts; no OAuth/session service is exposed yet."""

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from uuid import UUID

import jwt
import pytest
from fastapi.testclient import TestClient
from server_browser_models.models import JoinTicketClaims

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
    app.browser_api.signing_keys = None
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
