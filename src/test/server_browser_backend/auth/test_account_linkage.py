"""Provider associations are read independently, never taken from client claims."""
import io
import json
from unittest.mock import Mock

import pytest

from server_browser_backend.auth.game_identity import (
    GameIdentityUnavailable,
    InvalidGameCredential,
    PlayFabIdentityVerifier,
    VerifiedGameIdentity,
)

STEAM = "76561197993652680"


class Response(io.BytesIO):
    status = 200


def verifier(pairs):
    instance = PlayFabIdentityVerifier("operator-session")
    instance._opener = Mock()
    instance._opener.open.return_value = Response(
        json.dumps({"code": 200, "data": {"Data": pairs}}).encode()
    )
    return instance


def pair(**changes):
    return {"SteamStringId": STEAM, "PlayFabId": "a1b2", **changes}


def test_reads_provider_mapping_with_the_operator_session():
    instance = verifier([pair()])
    identity = VerifiedGameIdentity("A1B2")
    assert instance.verify_steam_link(identity, STEAM) == VerifiedGameIdentity("A1B2", STEAM)
    request = instance._opener.open.call_args.args[0]
    assert request.full_url == "https://EBF8D.playfabapi.com/Client/GetPlayFabIDsFromSteamIDs"
    assert request.get_header("X-authorization") == "operator-session"
    assert json.loads(request.data) == {"SteamStringIDs": [STEAM]}
    assert instance._opener.open.call_args.kwargs == {"timeout": 5}
    assert identity.linked_steam_id is None


@pytest.mark.parametrize("pairs", [[], [pair(PlayFabId=None)], [pair(PlayFabId="CAFE")]])
def test_missing_or_mismatched_link_is_rejected(pairs):
    with pytest.raises(InvalidGameCredential):
        verifier(pairs).verify_steam_link(VerifiedGameIdentity("A1B2"), STEAM)


@pytest.mark.parametrize(
    "pairs",
    [
        None,
        {},
        [None],
        [pair(), pair()],
        [pair(SteamStringId="76561197993652681")],
        [pair(SteamStringId=int(STEAM))],
        [pair(PlayFabId=42)],
        [pair(PlayFabId="not-a-playfab-id")],
    ],
)
def test_malformed_or_ambiguous_provider_response_is_not_a_link(pairs):
    with pytest.raises(GameIdentityUnavailable):
        verifier(pairs).verify_steam_link(VerifiedGameIdentity("A1B2"), STEAM)


@pytest.mark.parametrize("steam", [None, "", 42, "0", "01", "-1", str(2**64), "1\n"])
def test_invalid_steam_identity_never_reaches_provider(steam):
    instance = verifier([pair()])
    with pytest.raises(InvalidGameCredential):
        instance.verify_steam_link(VerifiedGameIdentity("A1B2"), steam)
    instance._opener.open.assert_not_called()


def test_provider_read_failure_cannot_establish_linkage():
    instance = verifier([pair()])
    instance._opener.open.side_effect = OSError("operator-session")
    with pytest.raises(GameIdentityUnavailable) as error:
        instance.verify_steam_link(VerifiedGameIdentity("A1B2"), STEAM)
    assert "operator-session" not in str(error.value)
