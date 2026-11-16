# Game join validation

Opt-in PlayFab public-data account-control challenges and single-use admission
tickets. Joining-player session credentials stay in the client and go only to
PlayFab. This replaces the earlier bearer-forwarding prototype; it is separate
from Discord identity and legacy Matchmake compatibility tickets.

## Enable

Set `GAME_JOIN_TICKET_DATABASE` to a private writable SQLite file. Its parent
directory must exist; existing files must be regular files with no group/other
permissions. Also set:

- `GAME_JOIN_AUDIENCE`: the plugin's canonical backend URL, without trailing
  slash, query, fragment or embedded credentials.
- `GAME_JOIN_VERIFIER_SESSION_TICKET`: a legitimate **independent verifier
  account's** PlayFab client session for Chivalry title `EBF8D`, not a joining
  player's session and not a title secret.

The service is disabled (HTTP 503) without a database setting. Configuring the
database without the other settings rejects startup. Provision the verifier
through a legitimate login and restart with a replacement session when needed.
No automatic login, account creation, credential extraction or refresh service
is shipped. Expired/revoked verifier sessions fail closed with HTTP 503.

Run one backend worker: the live registry and request budgets are process-local.
Pending challenges are also process-local and are lost safely on restart.
SQLite redemption is atomic, but does not make the registry multiworker-safe.

Clients and servers explicitly opt in with plugin `--validated-player-identity`,
using `--server-browser-backend URL`. Servers also need `--register`. Use HTTPS;
literal loopback HTTP is allowed only for local tests. Opt-in authorizes temporary
public writes to the reserved PlayFab user-data key `UnchainedJoin_v1`; it does
**not** authorize forwarding the player's session to the backend. Ordinary
browser redirection still strips credentials and does not opt in.

## API

Defined in `assets/chiv2-server-browser-api.yaml`; Python/Rust clients, Python
interfaces, models and FastAPI routes are generated. No handwritten routes.

- `POST /api/v1/game-join-challenges`: claimed account, SHA-256 commitment to a
  private client-generated completion secret, audience and selected IP/port.
  Resolves exactly one live registration and captures its key generation. Returns
  a random challenge ID, server ID and 60-second expiry; this is not authentication.
- `POST /api/v1/game-join-tickets`: challenge ID and private completion secret.
  Checks the commitment, caller IP, expiry and unchanged registration. Uses the
  backend's verifier session to read the exact public proof from the claimed
  account via PlayFab. Consumes the challenge and issues a 60-second grant bound
  to that verified account and registration generation. Concurrent completion
  can issue only one grant. No PlayFab player credential field is accepted.
- `POST /api/v1/servers/{server_id}/game-join-tickets/redeem`: registration-key
  header plus grant and claimed PlayFab ID. Requires the current registration
  source IP and live lease. Checks/consumes under registry coordination. Never
  renews a lease or returns linked platform-account associations.
- Invalid challenge, completion secret or public proof: 401. Unknown/ambiguous target: 404. Invalid registration,
  ticket, account, generation, expiry or replay: 403. Request budget: 429.
  Unconfigured/upstream/storage unavailable: 503. Success responses: `no-store`.
- No automatic redemption retries. A lost successful response requires a fresh
  browser join and ticket; retrying a consumed grant cannot admit again.

Budgets: eight concurrent requests, 1,024 total requests per minute, 12 challenge
begins and 12 completions per source/minute, 120 redemptions per source/minute.
Pending challenges are bounded to 1,024 globally and 12 per source, not per
unauthenticated account claim. Ticket storage
defaults to 4,096 rows, four outstanding grants/account and 4 MiB. No raw
credentials, grants or upstream account/error bodies are logged or persisted.
Only grant digests, verified account IDs and server bindings are stored in SQLite.
Pending challenge commitments and bindings exist only in bounded process memory.

### Public proof format

The client generates a random 32-byte base64url secret (43 characters, no padding).
Its lowercase SHA-256 ASCII digest is `commitment`. The public value is:

```text
uc-proof-v1: + lowercase_hex(SHA256(UTF8(NUL_join(
  "unchained-playfab-proof-v1", audience, server_id, uppercase_playfab_id,
  challenge_id, commitment
))))
```

Both implementations compute this value; a backend cannot supply arbitrary
user-data keys or contents. The private secret is sent only to the configured
backend, never to PlayFab. Seeing the public hash is insufficient to complete a
challenge. Server-generation binding lives in the server-side challenge record.

The client writes `UnchainedJoin_v1` with `Permission: Public`, then attempts
completion and cleanup even on failure. It removes the key only when the current
value matches its proof and verifies absence afterward. An unrelated existing
value blocks the join rather than being overwritten; prior protocol-shaped
commitments may be replaced after a crash. No other keys or permissions change.

PlayFab provides no compare-and-swap for this key. Concurrent joins/backends may
overwrite or remove competing proofs and fail closed; they cannot make an
incorrect account proof pass. Crashes/network failures can leave a public hash.
The single reserved key bounds leftover storage. It reveals protocol use but
contains no redeemable grant, session token or private completion secret.

This proves account control through PlayFab, not a separately audited current
storefront entitlement or Torn Banner's complete ban/admission policy. The
verifier's own PlayFab session remains a sensitive operator-held bearer token.
Title API policy, quotas, write/read latency, session renewal and availability
remain deployment concerns; this is not a native PlayFab authentication protocol.

The Rust lifecycle SDK redeems with its private registration key, without an
accessor exposing that key. Plugin workers carry no Unreal pointers across HTTP;
native delegates remain game-thread-owned and bounded. Completion preserves the
game's weak-object check and typed ID factory/setter.

## Evidence

- Backend baseline: `e820a32` (main fetched 2026-11-15).
- `CompatibilityApi.matchmake` returns an untracked `uuid4()` as `Ticket`.
  It does not authenticate a game account or record a redemption.
- Existing `auth/sessions.py` binds sessions to verified Discord IDs. Those
  sessions do not prove ownership of a PlayFab, Steam, or EOS account.
- `/api/v1/auth/login` retires EOS login with HTTP 410. Do not silently reuse
  that retired contract or label a Discord identity as a game identity.
- A live Steam browser join through the plugin sent `PlayFabId` and
  `UnofficialTicket`. The resulting replicated PlayerState had valid base and
  platform IDs but an invalid PlayFab ID. Missing URL options did not explain it.
- The native URL builder reads `UnofficialTicket` from the signed-in PlayFab
  account's attributes. A scratch Matchmake redirect saw no request during an
  automated browser join. The backend UUID is therefore not proven to be the
  observed URL ticket; do not assume the Matchmake handler is on that path.

## Native integration boundary

Current Chivalry executable SHA-256:
`d82b5eaa122aaee15366499bbce34e325741fecd06d6b7b5490fc650b5afb48b`.
Addresses below are not a portable API; names are inferred from code.

- `0x1414f0c70` looks up the native PlayFab subsystem, its session interface,
  a named session, and a session-associated authentication entry. Missing
  prerequisites return false before an HTTP request can be built.
- When prerequisites exist, it calls `0x141370340`, which uses an OpenAPI
  `/ConfirmJoinTicket` endpoint. This is not PlayFab's public Server API
  `AuthenticateSessionTicket` operation.
- Request serializer `0x1413bf900` emits `PlayFabId`, `Ticket`, and
  `EosIdentity`. Do not treat the third argument as an arbitrary platform ID.
- Completion at `0x1414f73f0` reads a boolean at response object `+0x38` and
  executes the bound completion delegate.
- The server path at `0x14193b120` and native PlayFab setter at `0x141a51ac0`
  were probed during an automated native browser join at 22:41:05 local time
  on 2026-11-15. The confirmation helper received all three non-empty arguments
  but returned false. Server initialization left base/PlayFab/platform validity
  at `[true, false, false]`; the client then sent a valid platform ID. The
  false-return paths precede HTTP submission. A further automated join at
  22:48:30 found the named session present but its session-authentication map
  entry missing. This is not an observed backend HTTP rejection.

Adding an endpoint alone cannot repair missing native session prerequisites.
Prefer a narrow asynchronous plugin adapter that preserves native completion
and typed ID assignment over fabricating native session/authentication state.
Never return unconditional success or invoke a success delegate for a claimed ID.

## Earlier bearer-forwarding experiment

PlayFab documents `Client/GetAccountInfo` with an `X-Authorization` client
session ticket. An empty request body returns the authenticated caller's
account. No title secret is documented for this operation:

<https://learn.microsoft.com/en-us/rest/api/playfab/client/account-management/get-account-info?view=playfab-rest>

The loopback experiment succeeded with the live native client credential on
2026-11-15: authenticated PlayFab ID present and linked Steam ID present.
Only those flags and verification status were logged. Neither the credential
nor the account response was persisted. This proves availability for the
tested Steam account/title at that time, not all clients or deployments.

The current backend no longer accepts that credential. `GetAccountInfo` remains
a direct client-to-PlayFab step that derives the local account before publishing
a proof. Server-side account-control verification uses `Client/GetUserData` and
the independent verifier session instead.

Upstream contracts: PlayFab/API_Specs revision
`80e104aaec1278bd184843809d40344fb129db20`,
`Swagger/PlayFab/Client.swagger.json` (`GetAccountInfo`, `GetUserData`,
`UpdateUserData`). Public SDK cross-check:
PlayFab/XPlatCppSdk revision `06d850bb770752726cfdbe4a0b2be08df5d59d47`,
`code/source/playfab/PlayFabClientApi.cpp`.

## Admission flow

1. Client obtains its own account directly from PlayFab and checks it matches the
   native join options. It begins and publishes the bound account-control proof.
   The backend reads that proof independently, not from a client assertion.
2. An explicit join-ticket operation issues a cryptographically random opaque
   ticket bound to that verified identity and the selected live server
   registration/generation. Integrate it with the actual browser-selection
   path; the legacy Matchmake route is not proven to run for these joins.
3. The server authenticates redemption using its existing registration key.
   Atomically check target server, expiry, identity claim, and unspent status.
   A failed wrong-server or wrong-identity attempt must not spend a valid ticket.
4. Return only the verified identity needed for the native setter. The plugin
   completes on the game thread, rechecks controller lifetime/connection identity,
   and uses native typed factories and setters. Ignore late completions after
   disconnect, travel, or controller replacement.
5. Keep compatibility-mode UUID tickets explicitly unverified. They must never
   be accepted by the verified-redemption path or grant account permissions.

Ticket storage needs bounded capacity and expiry cleanup, atomic redemption
across workers, hashed secrets, rate limits, and a defined retry policy for lost
responses. An in-process dictionary is not sufficient for multiworker production.
Server-key rotation/removal must invalidate outstanding grants for that generation.

## Components

- `auth/game_identity.py`: fixed-title HTTPS `GetUserData` proof verification
  with the verifier's independent session, no redirects/proxies, bounded response
  size, finite timeout and sanitized failures. Missing, private or mismatched
  proofs fail closed. It returns only the canonical PlayFab ID; it grants no
  EOS identity or storefront-ownership claim.
- `auth/game_join_tickets.py`: private bounded SQLite store, random 256-bit
  opaque tickets stored only as SHA-256 digests, 60-second default expiry,
  global/per-account quotas, bounded cleanup, and atomic one-time redemption.
  Grants bind to a server ID, registration-generation digest, and verified
  PlayFab ID. Wrong-server/account/generation failures do not consume grants.
  Workers must share the database and persisted limits.
- `auth/game_join.py` authenticates live registrations through `ServerList`,
  derives generation from the real registration key, and bounds requests.
  Registry locks cover only bounded storage work, never upstream HTTP.
- Lost successful redemption responses require a new ticket. The core deliberately
  rejects replays rather than silently granting a second connection.
- `main.py` composes the opt-in service. Legacy Matchmake behavior and existing
  Discord sessions remain unchanged.

## Required tests

Earlier bearer-forwarding validation on 2026-11-15 (not current-protocol evidence):

- Full backend application suite: 650 passed, 4 skipped, 1 warning.
- Mypy: verifier, ticket store, coordinator, registry, handlers and composition pass.
- Live native-credential verification: succeeded for the tested Steam account.
- Native Steam browser join: real automatic SDK registration, live PlayFab
  verification, single-use redemption, native setter and client replication of
  all three valid ID fields observed. Fresh reconnects redeem again; travel to
  Courtyard retains valid client IDs. Live replay and unissued tickets on fresh
  and restored states are rejected; a subsequent valid join recovers.
  Epic/EOS and second-client observation remain untested.

- Invalid/expired upstream credential, timeout, malformed response, banned account.
- Caller A cannot claim caller B by supplying B's PlayFab ID.
- Random, expired, replayed, wrong-server, wrong-account, and legacy UUID tickets.
- Concurrent redemption yields one grant; rejected attempts do not consume it.
- Restart/multiworker behavior, quotas, cleanup, key rotation, no credential logs.
- Native browser Matchmake and confirmation completion, late response after travel,
  replicated PlayFab ID on a second client, Steam and Epic/EOS independently.

Further contract changes remain OpenAPI-first per `CONTRIBUTING.md`.

Current public-proof validation on 2026-11-16:

- Full backend suite: 662 passed, 4 skipped; mypy and generated-output checks pass.
- Plugin Windows/Wine library tests: 480 passed, 20 ignored; host integration:
  38 passed, including a shared backend/Rust proof-format vector.
- Cross-account public writes/reads worked between distinct Steam and Heroic EGS
  PlayFab logins in both directions; both temporary keys were removed.
- Native browser joins worked for Epic with the Steam verifier and Steam with
  the Epic verifier. Both redeemed grants, assigned valid native IDs and verified
  reserved-key cleanup. Verifier sessions were explicitly provisioned in memory
  by a scratch-only loopback control endpoint, not by the production API.
- A process-restart Steam reconnect also redeemed a fresh grant and retained
  valid IDs after waiting for the native server to close the previous connection.
  An immediate reconnect attempt before native logout did not complete admission;
  its exact cause was not established. Fresh public-proof issuance and cleanup
  succeeded in that attempt.
- Challenge/grant replay was rejected by the live service. Wrong completion
  secrets and absent public proofs returned 401; the removed bearer contract
  returned 400. Microsoft and normal UI leave/rejoin remain untested.
- Evidence: `/tmp/opencode/playfab-investigation/{cross-*-evidence.json,
  challenge-runtime-evidence.json,challenge-backend-evidence.json}`. Scratch
  diagnostics and provisioning are not shipped. No production deployment claimed.
