# Game account linkage

Independent PlayFab and EOS proofs do not establish that the provider associates
those accounts. Never infer a link from a client claim, display name, public
user-data value, or simultaneous control of two accounts.

## Steam lookup

PlayFab's published `Client/GetPlayFabIDsFromSteamIDs` operation accepts
`SteamStringIDs` and returns `Data` pairs containing `SteamStringId` and
`PlayFabId`. The request uses the operator's independent verifier session, not
the joining player's credential.

`PlayFabIdentityVerifier.verify_steam_link()` requires one exact Steam mapping
to the verified PlayFab account. Missing/mismatched associations reject the
proof; ambiguous, malformed or unavailable upstream responses fail closed.
Callers must separately verify PlayFab control and the EOS Connect proof from
which the Steam account ID originates.

This helper is not yet connected to signed admission issuance. Adding it does
not establish Epic linkage or change the current admission guarantees.

## Epic investigation

Read-only controlled-account probes inspect:

- Own and peer `GetAccountInfo` metadata, including the presence of OpenID,
  Steam and server-custom associations.
- `GetPlayFabIDsFromOpenIdSubjectIdentifiers` for the pinned EOS issuer and
  verified EOS PUID/external-account candidates.
- Steam mapping from both storefront sessions.

Only selected field names and equality results are retained. No raw account
responses, reusable credentials, or identity tokens are saved. Probes do not
link, unlink or create accounts. Writable custom/generic IDs are not evidence
of provider-authenticated linkage.

Runtime results are pending. A successful Steam mapping does not establish an
Epic mapping; an unavailable private field is not evidence that no link exists.

## Sources

- [PlayFab Steam lookup](https://learn.microsoft.com/en-us/rest/api/playfab/client/account-management/get-playfab-ids-from-steam-ids?view=playfab-rest).
- [PlayFab account metadata](https://learn.microsoft.com/en-us/rest/api/playfab/client/account-management/get-account-info?view=playfab-rest).
- [Pinned published Client API specification](https://github.com/PlayFab/API_Specs/blob/80e104aa/Legacy/PlayFab/Client.api.json).
