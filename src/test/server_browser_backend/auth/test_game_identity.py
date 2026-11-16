import http.client
import io
import json
import urllib.error
from unittest.mock import Mock

import pytest

from server_browser_backend.auth.game_identity import (
    GameIdentityUnavailable,
    InvalidGameCredential,
    PlayFabIdentityVerifier,
    VerifiedGameIdentity,
    _NoRedirect,
)


class Response(io.BytesIO):
    status = 200


PROOF = "uc-proof-v1:" + "a" * 64


def verifier(payload):
    instance = PlayFabIdentityVerifier("verifier-session")
    instance._opener = Mock()
    instance._opener.open.return_value = Response(json.dumps(payload).encode())
    return instance


def account(**changes):
    return {
        "code": 200,
        "data": {
            "Data": {
                "UnchainedJoin_v1": {"Value": PROOF, "Permission": "Public", **changes}
            }
        },
    }


def test_reads_claimed_account_with_independent_verifier_session():
    instance = verifier(account())
    result = instance.verify("a1b2", PROOF)
    assert result == VerifiedGameIdentity("A1B2")
    request = instance._opener.open.call_args.args[0]
    assert request.full_url == "https://EBF8D.playfabapi.com/Client/GetUserData"
    assert json.loads(request.data) == {
        "PlayFabId": "A1B2",
        "Keys": ["UnchainedJoin_v1"],
    }
    assert request.get_header("X-authorization") == "verifier-session"
    assert instance._opener.open.call_args.kwargs == {"timeout": 5}


def test_linked_steam_is_optional_and_no_eos_identity_is_inferred():
    assert verifier(account()).verify("A1B2", PROOF) == VerifiedGameIdentity("A1B2")


@pytest.mark.parametrize(
    "credential", [None, "", "a" * 8193, "a\nb", "a\rb", "has space", "非ascii"]
)
def test_rejects_invalid_credentials_without_http(credential):
    with pytest.raises(ValueError, match="verifier session"):
        PlayFabIdentityVerifier(credential)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [],
        {"code": True},
        {"code": 400},
        {"code": 200, "data": {}},
        account(Value=None),
        account(Value=42),
        {"code": 200, "data": {"Data": []}},
        {"code": 200, "data": {"Data": {"UnchainedJoin_v1": []}}},
    ],
)
def test_rejects_malformed_success_responses(payload):
    with pytest.raises(GameIdentityUnavailable):
        verifier(payload).verify("A1B2", PROOF)


@pytest.mark.parametrize(
    "payload",
    [
        account(Permission="Private"),
        account(Value="wrong"),
        {"code": 200, "data": {"Data": {}}},
    ],
)
def test_rejects_missing_mismatched_or_private_proofs(payload):
    with pytest.raises(InvalidGameCredential):
        verifier(payload).verify("A1B2", PROOF)


@pytest.mark.parametrize(
    "status,expected",
    [
        (400, GameIdentityUnavailable),
        (401, GameIdentityUnavailable),
        (403, GameIdentityUnavailable),
        (302, GameIdentityUnavailable),
        (429, GameIdentityUnavailable),
        (500, GameIdentityUnavailable),
    ],
)
def test_sanitizes_http_errors(status, expected):
    instance = verifier(account())
    instance._opener.open.side_effect = urllib.error.HTTPError(
        instance.url,
        status,
        "private-session-ticket",
        {},
        io.BytesIO(b"sensitive-account-data"),
    )
    with pytest.raises(expected) as error:
        instance.verify("A1B2", PROOF)
    assert "private-session-ticket" not in str(error.value)
    assert "sensitive-account-data" not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.parametrize(
    "error",
    [OSError("secret"), TimeoutError("secret"), http.client.IncompleteRead(b"secret")],
)
def test_network_failures_are_not_authentication(error):
    instance = verifier(account())
    instance._opener.open.side_effect = error
    with pytest.raises(GameIdentityUnavailable, match="unavailable"):
        instance.verify("A1B2", PROOF)


def test_bounds_response_size():
    instance = verifier(account())
    instance._opener.open.return_value = Response(b" " * 65537)
    with pytest.raises(GameIdentityUnavailable, match="limit"):
        instance.verify("A1B2", PROOF)


def test_does_not_follow_credential_bearing_redirects():
    assert (
        _NoRedirect().redirect_request(
            None, None, 302, "", {}, "https://elsewhere.invalid"
        )
        is None
    )


@pytest.mark.parametrize(
    "title", ["https://example.invalid", "EBF8D/other", "", "a" * 17]
)
def test_endpoint_cannot_be_supplied_by_a_client(title):
    with pytest.raises(ValueError):
        PlayFabIdentityVerifier("verifier-session", title)
