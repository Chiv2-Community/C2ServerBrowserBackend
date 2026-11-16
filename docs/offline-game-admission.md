# Offline game admission

Backend signing and the Rust verifier are implemented. Plugin branch
`fix/validated-player-identity` now requests signed admissions, verifies them
locally and assigns native IDs while blocking the client platform-ID RPC.
Live Steam-host browser joins passed for Steam and Epic clients, including
authoritative ID replication, rejection of the demonstrated platform-RPC spoof
and fresh-process Epic reconnect. No online redemption occurred. Broader runtime
validation remains incomplete; this is not merge approval.

## Protocol

- Use the existing account-control challenge to verify the claimed PlayFab account.
  Joining players send their reusable PlayFab credentials only to fixed PlayFab HTTPS
  endpoints, never to this backend or a game host.
- Complete the challenge through `POST /api/v1/game-admissions`, supplying an EOS
  Connect ID token from `EOS_Connect_CopyIdToken` and the private completion secret.
  EOS Auth IDs and access tokens are not accepted as substitutes.
- Verify the EOS signature against the fixed Epic JWKS URL and require exact
  configured issuer, client, product, sandbox and deployment values.
  Derive the PUID from `sub` and the external identity from signed `act` claims.
  Currently allow Steam and Epic accounts; omit Discord and Microsoft Store.
- Sign an RS256 admission with `typ=unchained-game-join+jwt`, purpose
  `unchained.game-join`, version `1`, PlayFab `sub`, verified identities, timestamps,
  and a random UUID `jti`. Lifetime is at most 60 seconds and cannot exceed the EOS
  proof's remaining lifetime.
- Bind `aud` to `urn:unchained:server:<registration UUID>`. Each host process must
  obtain a fresh registration; never restore an old registration after restart.
- Publish public signing keys at `GET /api/v1/game-join-jwks.json`. The signing
  keyring is separate from the existing Discord signer. Retain rotated public keys
  until issued admissions expire and hosts have refreshed their snapshots.

Both proofs demonstrate account control. They do not, by themselves, establish a
provider-maintained link between the PlayFab account and EOS account, or current
game ownership. Do not describe independent proofs as proving those relationships.
Native token retrieval and signature/identity verification passed on both supported
clients. Required account linkage remains unresolved; do not deploy the native
admission path as proof of a provider-maintained account link.

## Host verifier

`server-browser-client-sdk::admission::AdmissionVerifier` performs no network or
disk I/O during admission. The host must fetch and install JWKS outside login.

- Pin issuer and registration UUID when creating the verifier.
- Refresh keys in the background; snapshots expire after five minutes.
- Fail closed on missing, stale or unknown keys. Never fetch during login.
- Accept only RS256 and the admission token type; reject JOSE extensions.
- Require exact issuer, audience, purpose and version, canonical identity fields,
  consistent subject, valid times, and a maximum 60-second lifetime.
- Consume `jti` atomically in one shared, process-local cache. Refreshing keys must
  not clear replay state. Capacity is 4096 unexpired admissions; exhaustion rejects
  new admissions rather than evicting live replay entries.
- Populate native fields only from returned claims. Reject client-to-server
  identity updates while retaining normal server-to-client replication.

JWTs remain bearer tokens. Signatures prevent forgery, not theft or first-use
redemption by an interceptor. No proof-of-possession transport is implemented.

## Backend configuration

Keep the existing `GAME_JOIN_VERIFIER_SESSION` and `GAME_JOIN_AUDIENCE`; the latter
is the exact trusted backend issuer URL, without a trailing slash.

For the new signed path, configure:

- `GAME_JOIN_SIGNING_KEYRING`: explicitly provisioned private RSA keyring path.
- `EOS_CONNECT_ISSUER`: exact EOS Connect issuer.
- `EOS_CONNECT_CLIENT_ID`, `EOS_CONNECT_PRODUCT_ID`, `EOS_CONNECT_SANDBOX_ID`,
  `EOS_CONNECT_DEPLOYMENT_ID`: operator-pinned game trust settings.

Isolated Steam and Epic runs on 2026-11-16 observed the same native SDK settings
and verified real Connect tokens against Epic's fixed JWKS:

```text
EOS_CONNECT_ISSUER=https://api.epicgames.dev/auth/v1/oauth
EOS_CONNECT_CLIENT_ID=7f2b13acf2e84ab0ae8604d822f10498
EOS_CONNECT_PRODUCT_ID=7b1bb546bd6547a4a7c2c4db55ca6c74
EOS_CONNECT_SANDBOX_ID=bd46d4ce259349e5bd8b3ded20274737
EOS_CONNECT_DEPLOYMENT_ID=70a4191f74d14a49940750942521a51b
```

These are observed public identifiers, not client-provided production overrides.
Evidence: `/tmp/opencode/eos-token-live/result.json`; raw tokens were not saved.

Do not derive these values from an unverified token in production. Use the existing
signing module's provisioning and rotation commands with a separate keyring.
Leave `GAME_JOIN_TICKET_DB` unset to disable opaque issuance/redemption. Those old
operations remain available for the unfinished plugin transition, not as an
authentication fallback after JWT rejection.

## Remaining integration and validation

- Settle required PlayFab/EOS account linkage; independent proofs are insufficient
  to claim a provider-maintained link.
- Runtime-test the plugin's signed issuance, registration-bound key-refresh/lease
  integration and synchronous verification under failures and key rotation.
- Run isolated browser joins, reconnect, restart, travel, key rotation, expiry,
  replay, mismatched proofs and identity-overwrite tests before merging.

Current live evidence: `/tmp/opencode/offline-authority/control/result.json`;
plugin implementation `a51ac33`, SDK pin `c8b3ca9`. The private test backend disabled
legacy opaque issuance/redemption. Epic-host Steam joins and the broader JWT
negative/travel matrix remain unvalidated.

The authoritative wire contract is
[`assets/chiv2-server-browser-api.yaml`](../assets/chiv2-server-browser-api.yaml).
Provider reference:
[EOS Connect](https://dev.epicgames.com/docs/game-services/connect/connect-reference).
