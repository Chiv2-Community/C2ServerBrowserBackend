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

Signed admission issuance uses this helper for Steam proofs before account
pinning. Epic proofs use independently verified control plus first-use pinning;
they are not represented as a provider-maintained association.

## First-use pinning

Signed admissions require `GAME_ACCOUNT_DATABASE`, an explicit durable SQLite
path shared by all backend workers. The parent directory must exist and be
private. The file must be a private regular file (created with mode 0600).
Back up this database; deleting it discards the established trust boundary.
Do not use a temporary path, restore an older snapshot casually, or share it
between unrelated PlayFab titles/EOS deployments. Do not enable the new backend
until the database path is provisioned; missing configuration fails startup.

After PlayFab control and EOS proof verification, the backend atomically checks:

- `user_accounts`: UUID `id`, unique `playfab_id`, nullable unique `steam_id`,
  unique `eos_id` (EOS PUID), `first_login_date`, `last_login_date`.
- A new nonconflicting combination is pinned on first accepted issuance.
- Matching issuance updates only the last-login timestamp. A verified Steam ID
  can be added to the same PlayFab/EOS pair if not pinned elsewhere. Epic logins
  without Steam never erase an existing Steam pin.
- Any conflicting pinned ID rejects issuance with HTTP 409, status
  `account_mismatch`, message `Account Mismatch`. The response reveals no stored
  IDs. No JWT is minted and no existing pin/login timestamp is changed.
- `validated_mismatches` retains a UUID, attempted verified PlayFab/Steam/EOS
  combination, reason, first/last mismatch timestamps and occurrence count.
  Repeated combinations update the same record, including nullable Steam IDs.
- Failed proofs and stale registrations create neither pins nor mismatch rows.
  Mismatch audit records commit despite admission rejection; pin/login changes
  roll back if signing fails. Concurrent first-use conflicts cannot both win.

Dates are UTC Unix seconds. Login dates mean successful backend admission
issuance, not confirmation that the game connection completed. No raw proofs,
JWTs or reusable player credentials are stored in these tables.

This is deliberately **trust on first use**: the first combination can be
provider-unlinked even when both proofs validate. Later conflicting combinations
are blocked; first-use poisoning is an accepted risk. The existing legacy opaque
route does not establish these pins and is not a fallback for signed rejection.

Default budgets are 100,000 pins, 100,000 distinct mismatches and 16,384 SQLite
pages. Workers must use identical persisted limits. Full, busy or corrupt storage
fails closed; pins/audits are never automatically evicted. Retention and access to
this identity database are operator responsibilities.

### Manual recovery

There is no public reassociation/reset API. Review the affected verified mismatch
and establish the correct account association through support. Stop all workers,
back up the database, and have an authorized operator make a deliberate correction
while preserving uniqueness and the mismatch history. Record the old/new values,
operator, time and reason in the support audit. Never automatically replace a pin
in response to a login attempt. Previously issued JWTs remain usable until expiry
(at most 60 seconds); existing host connections are not revoked by a correction.

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

Provider-backed Epic linkage therefore remains unresolved under the current
public-API and credential constraints. A supported title-authorized mapping
service or signed, independently verifiable association assertion would be needed
for that stronger claim. First-use pinning above is the chosen policy instead;
it does not justify labeling Epic admissions as provider-linked.

## Sources

- [PlayFab Steam lookup](https://learn.microsoft.com/en-us/rest/api/playfab/client/account-management/get-playfab-ids-from-steam-ids?view=playfab-rest).
- [PlayFab account metadata](https://learn.microsoft.com/en-us/rest/api/playfab/client/account-management/get-account-info?view=playfab-rest).
- [Pinned published Client API specification](https://github.com/PlayFab/API_Specs/blob/80e104aa/Legacy/PlayFab/Client.api.json).
- [Pinned published Server API specification](https://github.com/PlayFab/API_Specs/blob/80e104aa/Legacy/PlayFab/Server.api.json).
- [Pinned published Authentication API specification](https://github.com/PlayFab/API_Specs/blob/80e104aa/Legacy/PlayFab/Authentication.api.json).
