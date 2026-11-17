# Game account linkage

Deployment also requires the [player identity privacy review](player-identity-privacy.md).
Pins and mismatch records are personal-data processing, not anonymous telemetry.

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

Signed admissions require `GAME_ACCOUNT_HMAC_KEY_FILE` and `GAME_ACCOUNT_DATABASE`, an explicit durable SQLite
path shared by all backend workers. The parent directory must exist and be
private. The file must be a private regular file (created with mode 0600).
Back up this database; deleting it discards the established trust boundary.
Do not use a temporary path, restore an older snapshot casually, or share it
between unrelated PlayFab titles/EOS deployments. Do not enable the new backend
until the database path is provisioned; missing configuration fails startup.

After PlayFab control and EOS proof verification, the backend atomically checks:

- `user_accounts`: UUID `id`, unique `playfab_digest`, nullable unique
  `steam_digest`, unique `eos_digest` (EOS PUID), `first_login_date`, `last_login_date`.
- A new nonconflicting combination is pinned on first accepted issuance.
- Matching issuance updates only the last-login timestamp. A verified Steam ID
  can be added to the same PlayFab/EOS pair if not pinned elsewhere. Epic logins
  without Steam never erase an existing Steam pin.
- Any conflicting pinned ID rejects issuance with HTTP 409, status
  `account_mismatch`, message `Account Mismatch`. The response reveals no stored
  IDs. No JWT is minted and no existing pin/login timestamp is changed.
- `validated_mismatches` retains a UUID, attempted verified PlayFab/Steam/EOS
  digest combination, reason, first/last mismatch timestamps and occurrence count.
  Repeated combinations update the same record, including nullable Steam IDs.
- Failed proofs and stale registrations create neither pins nor mismatch rows.
  Mismatch audit records commit despite admission rejection; pin/login changes
  roll back if signing fails. Concurrent first-use conflicts cannot both win.

Dates are UTC Unix seconds. Login dates mean successful backend admission
issuance, not confirmation that the game connection completed. No raw proofs,
JWTs or reusable player credentials are stored in these tables.

### Identity digests and provisioning

Both tables store 32-byte HMAC-SHA-256 BLOBs, not raw IDs. The input is
`unchained-account-id-v1\0<provider>\0<canonical-id>` using ASCII bytes and provider
`playfab`, `steam` or `eos`. PlayFab IDs canonicalize to uppercase; EOS PUIDs must
be lowercase hexadecimal; Steam IDs use their validated decimal representation.
Provider verification and JWT issuance still use raw verified IDs transiently.

Provision a private 32-byte random key once, outside the database and its backups:

```sh
python -m server_browser_backend.auth.game_accounts init-key /private/keys/accounts.key
export GAME_ACCOUNT_HMAC_KEY_FILE=/private/keys/accounts.key
export GAME_ACCOUNT_DATABASE=/private/data/accounts.sqlite
```

The parent directories must already exist and be private. Do not use the signing
key as the HMAC key. All workers must use the same key; a domain-separated database
key check detects accidental replacement and fails startup. Provisioning never
overwrites a key, and startup never generates one. Back up the key separately with
restricted access: loss prevents matching existing pins. Key rotation is not
implemented; existing digests cannot be rehashed without the original IDs. Do not
delete the database or swap keys to rotate them.

For an existing plaintext database, stop **all writers**, preserve a private backup,
then migrate to a new path on the same deployment:

```sh
python -m server_browser_backend.auth.game_accounts migrate /private/data/accounts.sqlite /private/data/accounts-digests.sqlite --key /private/keys/accounts.key
export GAME_ACCOUNT_DATABASE=/private/data/accounts-digests.sqlite
```

Migration preserves UUIDs, timestamps, mismatch counts, limits and nullable Steam
associations; it publishes only a complete database and refuses an existing target.
Startup rejects the old schema rather than silently resetting pins. Verify counts,
correct logins and rejected conflicts before resuming service. The migration does
not modify or erase the plaintext source, snapshots, journals or backups: arrange
secure retirement under the operator's retention policy. Do not keep a public copy
or assume in-place SQL updates would remove plaintext from old SQLite pages.

HMAC is pseudonymisation, not anonymisation. Operators holding the key can match
known IDs, and association graphs/timestamps remain sensitive. No public digest
lookup API is added. Scoped support lookups can use `identity_digests()` with
verified/requester-authorized IDs; avoid logging those raw inputs.

This is deliberately **trust on first use**: the first combination can be
provider-unlinked even when both proofs validate. Later conflicting combinations
are blocked; first-use poisoning is an accepted risk. The existing legacy opaque
route does not establish these pins and is not a fallback for signed rejection.

Default budgets are 100,000 pins, 100,000 distinct mismatches and 16,384 SQLite
pages. Workers must use identical persisted limits. Full, busy or corrupt storage
fails closed; pins/audits are never automatically evicted. Retention and access to
this identity database are operator responsibilities. These are capacity limits,
not a justified retention schedule. There is currently no built-in expiry,
subject export, restriction or erasure workflow; resolve those deployment gaps
without silently resetting the first-use trust boundary.

### Manual recovery

There is no public reassociation/reset API. Review the affected verified mismatch
and establish the correct account association through support. Stop all workers,
back up the database, and have an authorized operator make a deliberate correction
while preserving uniqueness and the mismatch history. Record the old/new digests,
operator, time and reason in the support audit. Never automatically replace a pin
in response to a login attempt. Previously issued JWTs remain usable until expiry
(at most 60 seconds); existing host connections are not revoked by a correction.

### Live pinning validation

The HMAC-at-rest update passed 765 backend tests (5 skipped) and scoped type checks
for the changed production modules. Full-project mypy still reports the existing
`game_identity.py:109` `json.loads(body)` argument-type error.
Tests cover digest-only database pages, key provisioning/replacement rejection,
restart/concurrent pinning, and offline plaintext migration preserving history.
It does not change the admission wire contract. No new native game runtime pass
or migration of the earlier controlled-account database is claimed below.

Backend implementation `0077356` passed controlled Steam and Epic native browser
joins using the protocol-compatible plugin host/browser probes. Both pins retained
their UUIDs across a backend restart. A scratch request adapter then combined the
real controlled Steam PlayFab proof with the real controlled Epic EOS token;
production verification validated both proofs and rejected their pinned conflict.
One mismatch row committed, neither account row changed, and no host admission
occurred. A fresh Steam process subsequently joined with the correct combination.

Four admissions and one mismatch were observed, with zero online redemptions.
Games/backend were stopped. No raw tokens or reusable credentials were saved.
Evidence: `/tmp/opencode/account-pinning-runtime/{result.json,backend-evidence.json,run.log}`.
The updated plugin log message is compile-checked only; no native menu dialog was
added. Broader negative proofs/replay/rotation/travel cases remain unvalidated live.

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
