# Rust server browser client SDK

Handwritten lifecycle logic over `server-browser-client` protocol bindings.
Generation does not modify this crate. There is no Python lifecycle SDK yet.

```rust,no_run
use server_browser_client_sdk::{
    models::{Chivalry2Ports, ServerRegistrationRequest},
    Event, HttpEvent, HttpTransport, Policy, Registration, RequestFailure,
};
use std::sync::Arc;

# async fn example() -> Result<(), Box<dyn std::error::Error>> {
let request = ServerRegistrationRequest::new(
    Chivalry2Ports::new(7777, 7778, 7779),
    "My server".into(), "Community server".into(), "map".into(), 0, 32,
);
let transport = HttpTransport::new("https://browser.example", None)?;
let registration = Registration::new(transport, request, Policy::default())?;
let registration = Arc::new(registration.into_worker());
let worker = Arc::clone(&registration);
let task = tokio::spawn(async move {
    worker.run(|event| {
        match event {
            Event::Lifecycle(event) => println!("{event:?}"),
            Event::Http(HttpEvent::Register(Err(error))) => {
                eprintln!("Registration failed: {:?}", RequestFailure::from_error(error));
            }
            _ => {}
        }
        Ok(())
    }).await
});
// Publish metadata independently with registration.set_update(UpdateRegisteredServer { ... }).
// On application shutdown:
registration.cancel();
task.await??;
# Ok(())
# }
```

Applications collect game state and choose addresses/ports. The SDK serializes
registration, coalesced updates, heartbeats and deletion. It starts no hidden
threads or runtimes. Call this example from an application-owned Tokio runtime
with time and I/O enabled. `RegistrationWorker::run` owns scheduling and cleanup;
`set_update` coalesces metadata without waiting for HTTP. Keep metadata collection
outside the driver so slow collection cannot delay lease maintenance.
The worker runs once; cancellation/completion rejects further updates. Aborting
the driver closes it without hidden I/O; stranded identities expire server-side.
For lower-level control, use `Registration::run` with `RegistrationControl`, or
await `poll` and honor `next_delay`. `RegistrationTransport` returns `Send` futures; the monotonic
`Clock` remains injectable. A manager is spawnable when its transport and clock
are `Send`. Synchronous control methods only hold brief metadata mutexes.

## Observer events

`run` accepts one fallible observer. Match only the events you need:

- `Event::Lifecycle(LifecycleEvent)`: registration, renewal, loss and retry outcomes.
- `Event::Http(HttpEvent)`: `Register`, `Heartbeat`, `Update`, and `Delete` completions,
  including failed attempts and deletion HTTP 404.

Each HTTP variant borrows a route-specific `Result`: a generated success response
or `HttpError<RouteError>`. Errors retain their Display summary, source error,
HTTP status, raw response body and optional typed error entity. Payloads are borrowed
only during the callback; clone selected fields if needed. HTTP events precede
lifecycle processing. A successful registration's identity is retained before its
HTTP event so observer failure still permits cleanup.

Observers return `ObserverResult` (`Result<(), Box<dyn Error + Send + Sync>>`).
Keep them brief and nonblocking. Failure halts with `SdkError::ObserverFailed`;
the callback's error details are omitted from SDK diagnostics. The worker attempts
single-shot cleanup and reports its HTTP result through the same observer, even
after observer failure. Failed cleanup/observation never causes a second DELETE.

`Event`/`HttpEvent` Debug output redacts HTTP payloads. Generated responses/errors
do not: registration responses contain the secret key, and errors may include
credentials, URLs or response bodies. Log selected safe fields or use
`RequestFailure::from_error` for credential-safe error classification.
Low-level `poll` returns `LifecycleEvent`; `poll` and `stop` have no observer.

## Lifecycle policy

- Renew before the server lease deadline, at most every 30 seconds by default.
  Scheduling uses the difference between server timestamps and monotonic local
  time, not the client's wall clock.
- Metadata updates also renew the lease; no separate heartbeat is needed while
  updates succeed before the deadline. Each poll makes at most one request.
- Identical effective metadata is ignored. It sends no UPDATE and does not move
  the heartbeat deadline; the regular heartbeat keeps the registration alive.
  Omitted mods retain the previous list; an explicit empty list clears it.
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
   leaves expiry to the server. The worker attempts cleanup on terminal errors
   too; the lower-level `Registration::run` requires explicit `stop` on error.
- Dropping an in-flight registration future also leaves `RegistrationUncertain`;
  no blind retry is allowed. Dropping an update/heartbeat retains the known ID,
  last confirmed metadata and deadline. Dropping cleanup after it starts still
  consumes its one attempt. Dropping a never-polled future has no effect.

The default transport disables redirects and bounds requests to ten seconds.
Use `HttpTransport::with_user_agent` to identify an application without replacing
the bounded HTTP client or cloning its generated configuration.
It honors reqwest proxy settings; an optional source IP binds outgoing requests.
Use HTTPS outside loopback tests. Injected configurations own their timeout,
redirect and proxy policy. Do not log generated errors/configurations: they can
contain credentials. Lifecycle events/errors and manager Debug output omit keys
and response bodies. Custom transports must preserve that secrecy boundary.

Immutable registration metadata changes require stopping and constructing a new
manager. This SDK does not implement game hooks, discovery, Discord verification,
credential persistence, or authorization rules.

## Native compatibility URLs

For applications that must use the game's HTTP transport, `compatibility::tbio_base_url`
and `compatibility::playfab_matchmake_url` derive endpoints from generated operation
URL helpers. Both preserve deployment path prefixes and normalize trailing slashes.
They construct URLs only: applications still own native hooks, credentials and transport.
Generated clients use those same operation URL helpers when sending requests.

## Tests

```sh
cargo test --locked --manifest-path sdk/rust/Cargo.toml -p server-browser-client-sdk
uv run pytest -q src/test/server_browser_backend/test_sdk_e2e.py
```

The Python harness executes the otherwise ignored Rust integration test against
the actual backend over IPv4/IPv6 loopback, with ordinary and diagnostic listings.
