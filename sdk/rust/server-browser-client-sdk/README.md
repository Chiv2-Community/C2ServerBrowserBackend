# Rust server browser client SDK

Handwritten lifecycle logic over `server-browser-client` protocol bindings.
Generation does not modify this crate. There is no Python lifecycle SDK yet.

```rust,no_run
use server_browser_client_sdk::{
    models::{Chivalry2Ports, ServerRegistrationRequest},
    HttpTransport, Policy, Registration, RegistrationControl,
};

# async fn example() -> Result<(), Box<dyn std::error::Error>> {
let request = ServerRegistrationRequest::new(
    Chivalry2Ports::new(7777, 7778, 7779),
    "My server".into(), "Community server".into(), "map".into(), 0, 32,
);
let transport = HttpTransport::new("https://browser.example", None)?;
let mut registration = Registration::new(transport, request, Policy::default())?;
let control = RegistrationControl::default();
let worker_control = control.clone();
let worker = tokio::spawn(async move {
    let result = registration.run(&worker_control, |event| println!("{event:?}")).await;
    // run cleans up on cancellation; explicitly clean up after an error.
    let cleanup = registration.stop().await;
    result.and(cleanup)
});
// Publish live metadata with control.publish(UpdateRegisteredServer { ... }).
// On application shutdown:
control.cancel();
worker.await??;
# Ok(())
# }
```

Applications collect game state and choose addresses/ports. The SDK serializes
registration, coalesced updates, heartbeats and deletion. It starts no hidden
threads or runtimes. Call this example from an application-owned Tokio runtime
with time and I/O enabled. Use `run` in a caller-owned task or await `poll` and
honor `next_delay`. `RegistrationTransport` returns `Send` futures; the monotonic
`Clock` remains injectable. A manager is spawnable when its transport and clock
are `Send`. Synchronous control methods only hold brief metadata mutexes.

## Lifecycle policy

- Renew before the server lease deadline, at most every 30 seconds by default.
  Scheduling uses the difference between server timestamps and monotonic local
  time, not the client's wall clock.
- Metadata updates also renew the lease; no separate heartbeat is needed while
  updates succeed before the deadline. Each poll makes at most one request.
- Retry known-registration failures with bounded exponential backoff. Metadata
  changes do not bypass backoff. Defaults: 10–300 seconds, stop on the eighth
  consecutive failure; success resets the count. No jitter or Retry-After support
  is implemented yet.
- A 404 discards the old identity and permits re-registration. Other 4xx responses
  halt, except 429, which retries. In particular, 403 does not silently re-register.
- Keep the known identity after an ambiguous heartbeat/update, even beyond its
  last known deadline. The server may have renewed it before losing the response.
- Never automatically retry an ambiguous registration (network, decoding or 5xx
  failure). It may have succeeded. `RegistrationUncertain` requires operator
  recovery; do not repeatedly construct replacement managers. The protocol has
  no registration idempotency/recovery operation yet.
- `cancel` wakes waits; an in-flight request must finish or time out first.
  `stop` attempts deletion once. No network work occurs in `Drop`; failed cleanup
  leaves expiry to the server. `run` errors require explicit `stop`.
- Dropping an in-flight registration future also leaves `RegistrationUncertain`;
  no blind retry is allowed. Dropping an update/heartbeat retains the known ID,
  last confirmed metadata and deadline. Dropping cleanup after it starts still
  consumes its one attempt. Dropping a never-polled future has no effect.

The default transport disables redirects and bounds requests to ten seconds.
It honors reqwest proxy settings; an optional source IP binds outgoing requests.
Use HTTPS outside loopback tests. Injected configurations own their timeout,
redirect and proxy policy. Do not log generated errors/configurations: they can
contain credentials. Lifecycle events/errors and manager Debug output omit keys
and response bodies. Custom transports must preserve that secrecy boundary.

Immutable registration metadata changes require stopping and constructing a new
manager. This SDK does not implement game hooks, discovery, Discord verification,
credential persistence, or authorization rules.

## Tests

```sh
cargo test --locked --manifest-path sdk/rust/Cargo.toml -p server-browser-client-sdk
uv run pytest -q src/test/server_browser_backend/test_sdk_e2e.py
```

The Python harness executes the otherwise ignored Rust integration test against
the actual backend over IPv4/IPv6 loopback, with ordinary and diagnostic listings.
## Game identity admission

`Registration<HttpTransport>::redeem_game_join_ticket` calls the generated
redemption operation with the manager's private registration key. It rejects a
different server ID or stopped manager and never retries a consumed grant.
This is the older opaque-ticket path retained during native integration.
Discord sessions and legacy Matchmake tickets are not game proof.

For signed admissions, use `admission::AdmissionVerifier` with the trusted backend
issuer and a fresh registration UUID. Install JWKS snapshots outside login with
`replace_keys`; `consume` validates and consumes a JWT synchronously without I/O.
Share one verifier across login paths. Key refreshes retain replay state; missing,
unknown or stale keys and exhausted replay capacity fail closed. Never restore
the old registration UUID or reset replay state within a live registration.

Native proof retrieval, background key refresh and authoritative identity setters
still require plugin integration. See `docs/offline-game-admission.md` in the
repository for protocol, configuration and remaining runtime validation.
