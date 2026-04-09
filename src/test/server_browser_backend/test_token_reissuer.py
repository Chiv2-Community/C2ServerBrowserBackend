import pytest
import time
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from server_browser_backend.models.base_models import Jwk, JwksResponse
from server_browser_backend.token_reissuer import TokenReissuer

try:
    import jwt
except ImportError:
    jwt = None

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

