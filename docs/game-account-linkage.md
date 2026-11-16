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

### Live results, 2026-11-16

- Both Steam and Epic sessions read the controlled Steam account's exact
  Steam-to-PlayFab mapping successfully. This supports an independent verifier
  lookup, not merely an own-account read.
- Epic's own `GetAccountInfo` returned `Origination=ServerCustomId` and a
  `ServerCustomIdInfo.CustomId` exactly equal to the external-account ID in its
  independently verified EOS Connect JWT. It was not the EOS PUID.
- Cross-account reads succeeded but omitted the private association fields:
  neither session could read the other account's provider association this way.
- Both own-account responses omitted OpenID associations. The pinned EOS issuer
  plus either the PUID or external-account candidate returned no PlayFab mapping
  through `GetPlayFabIDsFromOpenIdSubjectIdentifiers` on either storefront.
  This tests those candidates only, not every possible issuer/configuration.
- Both EOS proofs verified against the fixed Epic JWKS. No account writes or
  account creation occurred; all private game processes were stopped.

Evidence: `/tmp/opencode/account-linkage/result.json`. Probe DLL SHA-256:
`6910d31ba1836c5d2b49bad270a9febe6debc8db5ed2a962b787a11ee6cedbdc`.
Only selected metadata/equality results were saved; no raw responses or tokens.

### Remaining trust boundary

The published `Server/GetPlayFabIDsFromServerCustomIDs` lookup requires the
title's `SecretKey`; so does `Server/GetUserAccountInfo`. A player or independently
provisioned verifier session cannot substitute for that credential.
`Authentication/ValidateEntityToken` is callable only by the title entity, not
an ordinary player entity. These are not deployable verifier routes without
title-owner cooperation.

An own-session comparison is useful diagnosis, but its boolean result or a
client-forwarded account response is not backend-verifiable evidence. Forwarding
the player's reusable session would violate the credential boundary. Do not use
either as a linkage workaround or create a new account link during admission.

Epic linkage therefore remains unresolved under the current public-API and
credential constraints. A supported title-authorized mapping service or signed,
independently verifiable association assertion is still needed. Steam lookup
availability does not justify labeling Epic admissions as provider-linked.

## Sources

- [PlayFab Steam lookup](https://learn.microsoft.com/en-us/rest/api/playfab/client/account-management/get-playfab-ids-from-steam-ids?view=playfab-rest).
- [PlayFab account metadata](https://learn.microsoft.com/en-us/rest/api/playfab/client/account-management/get-account-info?view=playfab-rest).
- [Pinned published Client API specification](https://github.com/PlayFab/API_Specs/blob/80e104aa/Legacy/PlayFab/Client.api.json).
- [Pinned published Server API specification](https://github.com/PlayFab/API_Specs/blob/80e104aa/Legacy/PlayFab/Server.api.json).
- [Pinned published Authentication API specification](https://github.com/PlayFab/API_Specs/blob/80e104aa/Legacy/PlayFab/Authentication.api.json).
