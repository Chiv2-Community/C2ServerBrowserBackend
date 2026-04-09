from __future__ import annotations
import time
import base64
from typing import Optional, Dict, Any, List, Union
from cryptography.hazmat.primitives.asymmetric import rsa
from server_browser_backend.models.base_models import Jwk, JwksResponse
from server_browser_backend.models.eos_models import EosIdTokenPayload

try:
    import jwt
    from jwt import PyJWKClient
except ImportError:
    jwt = None
    PyJWKClient = None

class TokenReissuer:
    def __init__(
        self, 
        private_key: rsa.RSAPrivateKey, 
        kid: str, 
        eos_jwks: Union[str, JwksResponse],
        issuer: str = "chivalry2-server-browser-backend",
        expected_pfpid: str = "7b1bb546bd6547a4a7c2c4db55ca6c74",
        expected_audience: Optional[str] = "7f2b13acf2e84ab0ae8604d822f10498",
        expected_issuer: str = "https://api.epicgames.dev/epic/oauth/v1"
    ) -> None:
        self.private_key = private_key
        self.public_key = private_key.public_key()
        self.kid = kid
        self.eos_jwks = eos_jwks
        self.issuer = issuer
        self.expected_pfpid = expected_pfpid
        self.expected_audience = expected_audience
        self.expected_issuer = expected_issuer

    def get_jwks_response(self) -> JwksResponse:
        numbers = self.public_key.public_numbers()
        
        def b64url_encode_int(i: int) -> str:
            byte_length = (i.bit_length() + 7) // 8
            b = i.to_bytes(byte_length, 'big')
            return base64.urlsafe_b64encode(b).decode('utf-8').replace('=', '')

        jwk = Jwk(
            kty="RSA",
            alg="RS256",
            use="sig",
            kid=self.kid,
            n=b64url_encode_int(numbers.n),
            e=b64url_encode_int(numbers.e)
        )
        return JwksResponse(keys=[jwk])

    def validate_and_reissue(self, eos_token: str, client_ip: str) -> str:
        if jwt is None:
            raise RuntimeError("PyJWT library not installed")

        from dataclasses import asdict

        # Get the signing key from the EOS JWKS
        if isinstance(self.eos_jwks, str):
            # It's a URL
            jwks_client = PyJWKClient(self.eos_jwks)
            signing_key = jwks_client.get_signing_key_from_jwt(eos_token)
            verify_key = signing_key.key
        else:
            # It's a JwksResponse object
            jwk_set = jwt.PyJWKSet.from_dict(asdict(self.eos_jwks))
            header = jwt.get_unverified_header(eos_token)
            signing_key = next(k for k in jwk_set.keys if k.key_id == header.get("kid"))
            verify_key = signing_key.key

        # Decode and validate EOS ID token
        payload_dict = jwt.decode(
            eos_token,
            verify_key,
            algorithms=["RS256"],
            audience=self.expected_audience,
            issuer=self.expected_issuer,
            options={
                "require": ["exp", "iat", "sub"],
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
            }
        )
        
        payload = EosIdTokenPayload.from_json(payload_dict)
        
        # Validate pfpid
        if payload.pfpid != self.expected_pfpid:
            raise jwt.InvalidTokenError(f"Invalid pfpid: {payload.pfpid}")

        # Issue our short-lived JWT (1 minute)
        now = int(time.time())
        our_payload = {
            "iss": self.issuer,
            "sub": payload.sub,
            "dn": payload.dn,
            "iat": now,
            "exp": now + 60,
            "ip": client_ip
        }
        
        our_token = jwt.encode(
            our_payload,
            self.private_key,
            algorithm="RS256",
            headers={"kid": self.kid}
        )
        
        return our_token
