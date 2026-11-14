# Discord authentication: implementation foundation

Tracks backend [#11](https://github.com/Chiv2-Community/C2ServerBrowserBackend/issues/11)
and [#12](https://github.com/Chiv2-Community/C2ServerBrowserBackend/issues/12), and
plugin [#34](https://github.com/Chiv2-Community/UnchainedPlugin/issues/34).

## Current boundary

Implemented: explicit persistent signing-key provisioning, bounded overlapping
rotation, public JWKS discovery, generated join-claim models, an internal
join-ticket signer, and a bounded transactional session store. Independent
workers observe atomic keyring replacements and serialized session writes.

Not implemented: Discord OAuth, client handoff, public session/ticket operations,
plugin validation/admission, or launcher policy configuration. No HTTP operation
can mint join tickets. Do not enable required Discord authentication yet.

## Provisioning

Provision with the installed backend package on the Linux backend host, using
the same filesystem and user as the deployment. Private material never belongs
in source control, an image layer, command arguments, or logs.

```sh
install -d -m 700 /srv/server-browser/auth
python -m server_browser_backend.auth.signing init /srv/server-browser/auth/signing.json
```

The file contains the active RSA private key and retained verification-only keys.
It has mode 0600; group/other access is rejected on POSIX. Restrict its directory
to trusted operators and the backend user. Secure backup copies equally.

Configure `DISCORD_SIGNING_KEYRING` to the file's runtime path. For Docker, mount
the **directory**, not the individual file, so atomic replacements are visible.
For example, bind `/srv/server-browser/auth` read-only at `/config/auth` and set:

```text
DISCORD_SIGNING_KEYRING=/config/auth/signing.json
```

Unset means signing is unavailable and `/api/v1/auth/jwks.json` returns
`{"keys": []}`. A missing, unreadable, malformed, oversized, or insecure configured
keyring fails startup explicitly. No ephemeral replacement is generated.
These settings enable key publication only, not login or admission.

## Rotation and recovery

```sh
python -m server_browser_backend.auth.signing rotate /srv/server-browser/auth/signing.json
```

- Cooperating writers serialize with a filesystem lock. Readers use atomic
  snapshots, reloading when file identity or metadata changes.
- Rotation creates a fresh RSA-2048 key and random key ID. The previous key's
  **public** part remains published for 90 seconds: ticket lifetime 60 seconds
  plus validator clock tolerance 30 seconds. Its private part is removed.
- The keyring is limited to eight keys and 64 KiB. Excess rotation fails without
  evicting keys that may still validate tickets; retry after their overlap ends.
- Temporary files are private, flushed, atomically replaced, and directory
  metadata is flushed. Replacement failure leaves the old keyring usable.
- JWKS contains public RSA numbers only and uses `Cache-Control: no-store`.
  Validators still need bounded caching and rate-limited refresh on unknown IDs.
- Back up the keyring after provisioning/rotation. Restoring an old backup can
  invalidate newer tickets; prefer rotating the current keyring normally.
- For compromise recovery, replace the keyring deliberately and restart/reload
  validators as needed. Cached public keys can remain trusted until their
  configured expiry; key replacement is not instantaneous revocation.

The registry itself remains process-local. Persistent signing keys do **not**
make the full service multi-worker-safe; keep `UVICORN_WORKERS=1` until registry
and authentication session storage have appropriate shared ownership.

## Join ticket contract

The OAS `JoinTicketClaims` schema is authoritative for claim names/types.
The internal signer accepts only a verified session's Discord ID, its original
authentication time, an explicitly configured HTTPS issuer, and a current
server registration UUID. Callers must not expose arbitrary claim signing.

| Field | Contract |
| --- | --- |
| Header `alg` | `RS256`, fixed allowlist; never accept `none` or HMAC |
| Header `typ` | `unchained-join+jwt` |
| Header `kid` | Random UUID from the trusted issuer keyring |
| `iss` | Explicit fixed HTTPS issuer, exact comparison; no token-supplied trust URLs |
| `sub` | Verified Discord snowflake, canonical unsigned 64-bit decimal string |
| `aud` | `urn:unchained:server:<registration UUID>` |
| `purpose` | `unchained.join` |
| `auth_time` | Original Discord authentication timestamp, unchanged by refresh |
| `iat`, `nbf` | Issuance timestamp in Unix seconds |
| `exp` | `iat + 60` seconds |
| `jti` | Fresh random UUID for atomic one-use consumption |

Audience identifies a **live registration incarnation**, not a hostname/IP or
Discord guild. Heartbeats retain it; server restart/re-registration changes it
and requires a fresh ticket. Plugin discovery/direct joins must agree on this
mapping before public issuance is added. Never reuse engine/platform identifiers
as Discord identities. Hosts authorize guild/role/age/ban policy with their own
bots; those mutable policies are not permanent issuer claims.

Future validators must check every field above, required claims and types,
signature, maximum lifetime, and clock tolerance. They must not trust `jku`,
`x5u`, embedded keys, or an issuer selected by the token. Consume `jti` atomically
with admission and retain bounded replay entries through `exp + 30`.
These are requirements for plugin #36, not a claim that validation is implemented.

## Remaining protocol and rollout gates

Plugin #34 must demonstrate native prompt/browser launch, cancellation,
asynchronous join resumption, practical join-option size, and binding from
admitted connection to player/controller across travel. Native Windows and
Steam/Epic/Proton round trips have not been tested for this feature.

The current join JWT is a bearer credential. Game transport confidentiality and
whether proof-of-possession/connection binding is necessary remain a **blocking
design gate** before activation; signatures and one-use IDs alone do not prevent
an intercepted unused ticket being raced onto another connection.

Backend #12 must deliver OAuth state/PKCE where supported, browser completion
bound to the initiating client, and bounded transactional session storage as one
unit. Persist only credential hashes; rotate opaque refresh credentials with
documented retry/reuse rules, absolute/idle expiry, per-account caps, global/IP
limits, concurrency limits, cleanup, and storage budgets. Never activate an
unbounded interim in-memory session store. Do not retain Discord access tokens
after identification or send refresh credentials to game servers.

Host authentication modes remain exactly **disabled** or **required**. Required
mode fails closed; disabled mode preserves legacy joins without inventing a
verified identity. Plugin #35–#38 and launcher #182 remain rollout prerequisites.

## Internal session storage

`auth.sessions.SessionStore` is not wired into HTTP startup or exposed through
an API. It is a tested storage boundary for backend #12, not a completed login
service. Only an OAuth handler that has verified the Discord identity may create
a session. Before exposing it, add OAS-defined operations, bound the pending
login store and all HTTP/network work, and enforce IP/account/global rate limits.

The database must be a local SQLite file in a private directory, with mode 0600.
Use one shared file for all workers on one host, not NFS or independent replicas.
Every connection enforces foreign keys, full synchronization, a bounded page
count, and a 2 MiB page cache. A one-second SQLite lock timeout bounds waiting.
Rollback-journal mode avoids unbounded WAL growth. Backups need the same access
control as signing keys; restoring a backup can resurrect revoked credentials.
Do not restore sessions for compromise recovery: revoke/recreate them instead.

Default hard limits (persisted and checked against every worker's configuration):

| Resource | Limit |
| --- | --- |
| Live sessions | 1,024 globally, 4 per Discord account |
| Credential hashes | 65,536 globally, 256 per session including its current hash |
| Database | 16,384 pages of 4,096 bytes: 64 MiB |
| Idle / absolute lifetime | 24 hours / 7 days |
| Minimum refresh rotation interval | 60 seconds |
| Cleanup per transaction | At most 32 expired families, each with bounded history |

Allow disk space for both the database and rollback journal (up to roughly twice
the database cap), plus filesystem overhead and backups. HTTP concurrency limits
must also bound the number of connections/page caches before activation.

Refresh credentials are opaque random 256-bit values. Only SHA-256 digests are
stored; raw values are returned once and omitted from result representations.
All quota checks, rotation, and family revocation execute in `BEGIN IMMEDIATE`
transactions. Creation rejects full capacity without evicting valid sessions.
Refresh extends idle expiry only up to the original absolute expiry; neither
refresh nor ticket authentication changes `auth_time`.

Every spent hash remains until its family expires or is revoked. On the history
cap, refresh fails without changing the current credential; the client must
reauthenticate and retire the old session. No unexpired history is silently
discarded to make room. Explicit bounded cleanup removes expired sessions and
their hashes; cleanup failure rolls back the enclosing operation.

### Retry and lost responses

- Serialize refresh and credential replacement in the client.
- A too-soon refresh returns a retry delay internally and does not rotate or
  revoke. Keep the current credential and wait before retrying.
- Any retained spent credential presented for refresh or authentication revokes
  the entire family, including a descendant returned by a concurrent winner.
- There is no response-recovery grace window and no persisted replacement secret.
  If a successful rotation response is lost, reauthenticate. Blindly retrying
  the old credential revokes its descendants. OAuth/UI must make this recoverable.
- Quota/storage-full failures preserve the current credential. Storage-busy
  failures roll back and return a distinct internal error. Public HTTP mappings
  and idempotency behavior must be defined in OAS before exposing these methods.
- Logout accepts a current or retained credential and deletes its whole family.
  Repeated logout is idempotent. Already issued join JWTs can remain valid until
  their expiry even after logout/replay revocation.
