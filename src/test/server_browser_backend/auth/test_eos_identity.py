import json
import time
from unittest.mock import MagicMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from server_browser_backend.auth.eos_identity import EosConnectVerifier, JWKS_URL
from server_browser_backend.auth.game_identity import (
    GameIdentityUnavailable,
    InvalidGameCredential,
)


@pytest.fixture
def proof():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = EosConnectVerifier(
        issuer="https://api.epicgames.dev/auth/v1",
        client_id="client",
        product_id="product",
        sandbox_id="sandbox",
        deployment_id="deployment",
    )
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="key", alg="RS256", use="sig")
    verifier._opener = MagicMock()
    response = verifier._opener.open.return_value.__enter__.return_value
    response.status = 200
    response.read.return_value = json.dumps({"keys": [jwk]}).encode()
    now = int(time.time())
    claims = dict(
        iss=verifier.issuer,
        aud="client",
        sub="a" * 32,
        iat=now,
        exp=now + 300,
        pfpid="product",
        pfsid="sandbox",
        pfdid="deployment",
        act={"eat": "steam", "eaid": "76561198000000001"},
    )

    def token(changes=None, headers=None, signing_key=None):
        return jwt.encode(
            {**claims, **(changes or {})},
            signing_key or key,
            algorithm="RS256",
            headers={"kid": "key", **(headers or {})},
        )

    return verifier, claims, token


def test_verified_steam_and_epic_identity(proof):
    verifier, _, token = proof
    steam = verifier.verify(token())
    assert steam.product_user_id == "a" * 32
    assert (steam.platform_provider, steam.platform_id) == (
        "steam",
        "76561198000000001",
    )
    epic = verifier.verify(token({"act": {"eat": "epicgames", "eaid": "b" * 32}}))
    assert (epic.platform_provider, epic.platform_id) == ("eos", "a" * 32)
    verifier._opener.open.assert_called_once_with(JWKS_URL, timeout=5)


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://attacker.invalid"},
        {"aud": "other"},
        {"aud": ["client"]},
        {"pfpid": "other"},
        {"pfsid": "other"},
        {"pfdid": "other"},
        {"sub": "not-a-puid"},
        {"sub": None},
        {"exp": 1},
        {"exp": True},
        {"iat": True},
        {"iat": 9999999999},
        {"nbf": 9999999999},
        {"act": {}},
        {"act": []},
        {"act": {"eat": "xbl", "eaid": "123"}},
        {"act": {"eat": "steam", "eaid": "18446744073709551616"}},
        {"act": {"eat": "steam", "eaid": "0"}},
        {"act": {"eat": "steam", "eaid": 76561198000000001}},
        {"act": {"eat": "epicgames", "eaid": "not-an-account"}},
    ],
)
def test_rejects_untrusted_claims(proof, changes):
    verifier, _, token = proof
    with pytest.raises(InvalidGameCredential):
        verifier.verify(token(changes))


@pytest.mark.parametrize(
    "headers",
    [
        {"kid": "unknown"},
        {"jku": "https://attacker.invalid"},
        {"jwk": {}},
        {"crit": ["unknown"]},
        {"x5u": "https://attacker.invalid"},
    ],
)
def test_rejects_key_substitution(proof, headers):
    verifier, _, token = proof
    with pytest.raises(InvalidGameCredential):
        verifier.verify(token(headers=headers))


def test_rejects_wrong_signature_and_unsigned_tokens(proof):
    verifier, claims, token = proof
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    for invalid in (
        token(signing_key=other),
        jwt.encode(claims, "", algorithm="none"),
        "bad",
    ):
        with pytest.raises(InvalidGameCredential):
            verifier.verify(invalid)


@pytest.mark.parametrize("body", [b"{}", b"{", b"x" * 65537, b'{"keys": []}'])
def test_malformed_jwks_fails_closed(proof, body):
    verifier, _, token = proof
    verifier._opener.open.return_value.__enter__.return_value.read.return_value = body
    with pytest.raises(GameIdentityUnavailable):
        verifier.verify(token())


def test_jwks_outage_fails_closed(proof):
    verifier, _, token = proof
    verifier._opener.open.side_effect = OSError("unavailable")
    with pytest.raises(GameIdentityUnavailable):
        verifier.verify(token())
