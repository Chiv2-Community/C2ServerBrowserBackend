import pytest
import time
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from server_browser_api.models import Jwk, JwksResponse
from server_browser_backend.token_reissuer import TokenReissuer

import jwt
from fastapi.testclient import TestClient
from server_browser_api.runtime import DictTypeError


@pytest.fixture
def eos_payload():
    now = int(time.time())
    return {
        "sub": "test-user",
        "pfsid": "test-sandbox",
        "iss": "https://api.epicgames.dev/epic/oauth/v1",
        "dn": "Test User",
        "nonce": "test-nonce",
        "pfpid": "7b1bb546bd6547a4a7c2c4db55ca6c74",
        "aud": "7f2b13acf2e84ab0ae8604d822f10498",
        "pfdid": "test-deployment",
        "appid": "test-app",
        "exp": now + 3600,
        "iat": now,
        "jti": "test-jti",
    }


@pytest.mark.parametrize("act_claim", [
    pytest.param({}, id="omitted"),
    pytest.param({"act": None}, id="null"),
    pytest.param({"act": {
        "eat": "epic", "eaid": "external-id", "pltfm": "steam", "dty": "desktop",
    }}, id="populated"),
])
def test_login_external_account_claim(
    app_factory, private_key, eos_private_key, eos_jwks, eos_payload, act_claim,
):
    reissuer = TokenReissuer(private_key=private_key, kid="test-kid", eos_jwks=eos_jwks)
    app = app_factory(token_reissuer=reissuer)
    token = jwt.encode(
        {**eos_payload, **act_claim}, eos_private_key,
        algorithm="RS256", headers={"kid": "eos-key-1"},
    )
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        response = client.post("/api/v1/auth/login", json={"token": token})
    assert response.status_code == 200
    decoded = jwt.decode(response.json()["token"], private_key.public_key(), algorithms=["RS256"])
    assert decoded["sub"] == "test-user"
    assert decoded["dn"] == "Test User"
    assert decoded["ip"] == "127.0.0.1"
    assert decoded["iss"] == "chivalry2-server-browser-backend"
    assert decoded["exp"] - decoded["iat"] == 60


@pytest.mark.parametrize("claim, value, error", [
    ("iss", "wrong-issuer", jwt.InvalidIssuerError),
    ("aud", "wrong-audience", jwt.InvalidAudienceError),
    ("exp", 0, jwt.ExpiredSignatureError),
    ("iat", 4102444800, jwt.ImmatureSignatureError),
    ("pfpid", "wrong-product", jwt.InvalidTokenError),
])
def test_null_external_account_preserves_claim_validation(
    private_key, eos_private_key, eos_jwks, eos_payload, claim, value, error,
):
    reissuer = TokenReissuer(private_key=private_key, kid="test-kid", eos_jwks=eos_jwks)
    token = jwt.encode(
        {**eos_payload, "act": None, claim: value}, eos_private_key,
        algorithm="RS256", headers={"kid": "eos-key-1"},
    )
    with pytest.raises(error):
        reissuer.validate_and_reissue(token, "127.0.0.1")


@pytest.mark.parametrize("claims", [
    {"act": None, "dn": None},
    {"act": {}},
    {"act": {"eat": "epic", "eaid": "external-id", "pltfm": "steam", "dty": None}},
])
def test_external_account_nullability_is_scoped(
    private_key, eos_private_key, eos_jwks, eos_payload, claims,
):
    reissuer = TokenReissuer(private_key=private_key, kid="test-kid", eos_jwks=eos_jwks)
    token = jwt.encode(
        {**eos_payload, **claims}, eos_private_key,
        algorithm="RS256", headers={"kid": "eos-key-1"},
    )
    with pytest.raises(DictTypeError):
        reissuer.validate_and_reissue(token, "127.0.0.1")


def test_null_external_account_requires_valid_signature(private_key, eos_jwks, eos_payload):
    reissuer = TokenReissuer(private_key=private_key, kid="test-kid", eos_jwks=eos_jwks)
    token = jwt.encode(
        {**eos_payload, "act": None}, private_key,
        algorithm="RS256", headers={"kid": "eos-key-1"},
    )
    with pytest.raises(jwt.InvalidSignatureError):
        reissuer.validate_and_reissue(token, "127.0.0.1")

@pytest.fixture
def private_key():
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

@pytest.fixture
def eos_private_key():
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

@pytest.fixture
def eos_jwks(eos_private_key):
    numbers = eos_private_key.public_key().public_numbers()
    def b64url_encode_int(i):
        import base64
        byte_length = (i.bit_length() + 7) // 8
        b = i.to_bytes(byte_length, 'big')
        return base64.urlsafe_b64encode(b).decode('utf-8').replace('=', '')

    return JwksResponse(
        keys=[
            Jwk(
                kty="RSA",
                alg="RS256",
                use="sig",
                kid="eos-key-1",
                n=b64url_encode_int(numbers.n),
                e=b64url_encode_int(numbers.e),
            )
        ]
    )

def test_token_reissuer_success(private_key, eos_private_key, eos_jwks):
    if jwt is None:
        pytest.skip("PyJWT not installed")

    reissuer = TokenReissuer(
        private_key=private_key,
        kid="test-kid",
        eos_jwks=eos_jwks
    )

    # Create a fake EOS token
    now = int(time.time())
    payload = {
        "sub": "test-user",
        "pfsid": "test-sandbox",
        "iss": "https://api.epicgames.dev/epic/oauth/v1",
        "dn": "Test User",
        "nonce": "test-nonce",
        "pfpid": "7b1bb546bd6547a4a7c2c4db55ca6c74", # Correct pfpid
        "aud": "7f2b13acf2e84ab0ae8604d822f10498",
        "pfdid": "test-deployment",
        "appid": "test-app",
        "exp": now + 3600,
        "iat": now,
        "jti": "test-jti"
    }
    eos_token = jwt.encode(payload, eos_private_key, algorithm="RS256", headers={"kid": "eos-key-1"})

    reissued_token = reissuer.validate_and_reissue(eos_token, "127.0.0.1")
    
    # Verify reissued token
    decoded = jwt.decode(reissued_token, private_key.public_key(), algorithms=["RS256"])
    assert decoded["sub"] == "test-user"
    assert decoded["dn"] == "Test User"
    assert decoded["ip"] == "127.0.0.1"
    assert decoded["iss"] == "chivalry2-server-browser-backend"

def test_token_reissuer_custom_issuer(private_key, eos_private_key, eos_jwks):
    if jwt is None:
        pytest.skip("PyJWT not installed")

    custom_issuer = "https://my-custom-domain.com"
    reissuer = TokenReissuer(
        private_key=private_key,
        kid="test-kid",
        eos_jwks=eos_jwks,
        issuer=custom_issuer
    )

    # Create a fake EOS token
    now = int(time.time())
    payload = {
        "sub": "test-user",
        "pfsid": "test-sandbox",
        "iss": "https://api.epicgames.dev/epic/oauth/v1",
        "dn": "Test User",
        "nonce": "test-nonce",
        "pfpid": "7b1bb546bd6547a4a7c2c4db55ca6c74",
        "aud": "7f2b13acf2e84ab0ae8604d822f10498",
        "pfdid": "test-deployment",
        "appid": "test-app",
        "exp": now + 3600,
        "iat": now,
        "jti": "test-jti"
    }
    eos_token = jwt.encode(payload, eos_private_key, algorithm="RS256", headers={"kid": "eos-key-1"})

    reissued_token = reissuer.validate_and_reissue(eos_token, "127.0.0.1")
    
    # Verify reissued token
    decoded = jwt.decode(reissued_token, private_key.public_key(), algorithms=["RS256"])
    assert decoded["iss"] == custom_issuer

def test_token_reissuer_invalid_pfpid(private_key, eos_private_key, eos_jwks):
    if jwt is None:
        pytest.skip("PyJWT not installed")

    reissuer = TokenReissuer(
        private_key=private_key,
        kid="test-kid",
        eos_jwks=eos_jwks
    )

    now = int(time.time())
    payload = {
        "sub": "test-user",
        "pfsid": "test-sandbox",
        "iss": "https://api.epicgames.dev/epic/oauth/v1",
        "dn": "Test User",
        "nonce": "test-nonce",
        "pfpid": "WRONG_PFPID", 
        "aud": "7f2b13acf2e84ab0ae8604d822f10498",
        "pfdid": "test-deployment",
        "appid": "test-app",
        "exp": now + 3600,
        "iat": now,
        "jti": "test-jti"
    }
    eos_token = jwt.encode(payload, eos_private_key, algorithm="RS256", headers={"kid": "eos-key-1"})

    with pytest.raises(jwt.InvalidTokenError, match="Invalid pfpid"):
        reissuer.validate_and_reissue(eos_token, "127.0.0.1")

def test_token_reissuer_expired(private_key, eos_private_key, eos_jwks):
    if jwt is None:
        pytest.skip("PyJWT not installed")

    reissuer = TokenReissuer(
        private_key=private_key,
        kid="test-kid",
        eos_jwks=eos_jwks
    )

    now = int(time.time())
    payload = {
        "sub": "test-user",
        "pfsid": "test-sandbox",
        "iss": "https://api.epicgames.dev/epic/oauth/v1",
        "dn": "Test User",
        "nonce": "test-nonce",
        "pfpid": "7b1bb546bd6547a4a7c2c4db55ca6c74",
        "aud": "7f2b13acf2e84ab0ae8604d822f10498",
        "pfdid": "test-deployment",
        "appid": "test-app",
        "exp": now - 3600, # Expired
        "iat": now - 7200,
        "jti": "test-jti"
    }
    eos_token = jwt.encode(payload, eos_private_key, algorithm="RS256", headers={"kid": "eos-key-1"})

    with pytest.raises(jwt.ExpiredSignatureError):
        reissuer.validate_and_reissue(eos_token, "127.0.0.1")

def test_token_reissuer_invalid_signature(private_key, eos_jwks):
    if jwt is None:
        pytest.skip("PyJWT not installed")

    another_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    
    reissuer = TokenReissuer(
        private_key=private_key,
        kid="test-kid",
        eos_jwks=eos_jwks
    )

    now = int(time.time())
    payload = {
        "sub": "test-user",
        "pfsid": "test-sandbox",
        "iss": "https://api.epicgames.dev/epic/oauth/v1",
        "dn": "Test User",
        "nonce": "test-nonce",
        "pfpid": "7b1bb546bd6547a4a7c2c4db55ca6c74",
        "aud": "7f2b13acf2e84ab0ae8604d822f10498",
        "pfdid": "test-deployment",
        "appid": "test-app",
        "exp": now + 3600,
        "iat": now,
        "jti": "test-jti"
    }
    # Sign with WRONG key
    eos_token = jwt.encode(payload, another_private_key, algorithm="RS256", headers={"kid": "eos-key-1"})

    with pytest.raises(jwt.InvalidSignatureError):
        reissuer.validate_and_reissue(eos_token, "127.0.0.1")

def test_token_reissuer_missing_claims(private_key, eos_private_key, eos_jwks):
    if jwt is None:
        pytest.skip("PyJWT not installed")

    reissuer = TokenReissuer(
        private_key=private_key,
        kid="test-kid",
        eos_jwks=eos_jwks
    )

    now = int(time.time())
    payload = {
        "sub": "test-user",
        # "exp": now + 3600, # Missing exp
        "iat": now,
        "pfpid": "7b1bb546bd6547a4a7c2c4db55ca6c74",
        "aud": "7f2b13acf2e84ab0ae8604d822f10498",
        "iss": "https://api.epicgames.dev/epic/oauth/v1",
    }
    eos_token = jwt.encode(payload, eos_private_key, algorithm="RS256", headers={"kid": "eos-key-1"})

    with pytest.raises(jwt.MissingRequiredClaimError, match="exp"):
        reissuer.validate_and_reissue(eos_token, "127.0.0.1")

def test_token_reissuer_with_external_account(private_key, eos_private_key, eos_jwks):
    if jwt is None:
        pytest.skip("PyJWT not installed")

    reissuer = TokenReissuer(
        private_key=private_key,
        kid="test-kid",
        eos_jwks=eos_jwks
    )

    now = int(time.time())
    payload = {
        "sub": "test-user",
        "pfsid": "test-sandbox",
        "iss": "https://api.epicgames.dev/epic/oauth/v1",
        "dn": "Test User",
        "nonce": "test-nonce",
        "pfpid": "7b1bb546bd6547a4a7c2c4db55ca6c74",
        "aud": "7f2b13acf2e84ab0ae8604d822f10498",
        "pfdid": "test-deployment",
        "appid": "test-app",
        "exp": now + 3600,
        "iat": now,
        "jti": "test-jti",
        "act": {
            "eat": "epic",
            "eaid": "external-id",
            "pltfm": "steam",
            "dty": "desktop"
        }
    }
    eos_token = jwt.encode(payload, eos_private_key, algorithm="RS256", headers={"kid": "eos-key-1"})

    reissued_token = reissuer.validate_and_reissue(eos_token, "127.0.0.1")
    decoded = jwt.decode(reissued_token, private_key.public_key(), algorithms=["RS256"])
    assert decoded["sub"] == "test-user"


def test_jwks_response(private_key):
    reissuer = TokenReissuer(
        private_key=private_key,
        kid="test-kid",
        eos_jwks=JwksResponse(keys=[])
    )
    
    jwks = reissuer.get_jwks_response()
    assert len(jwks.keys) == 1
    assert jwks.keys[0].kid == "test-kid"
    assert jwks.keys[0].kty == "RSA"
