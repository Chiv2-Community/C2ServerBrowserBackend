# Rust server browser client SDK

Handwritten lifecycle logic over `server-browser-client` protocol bindings.
Generation does not modify this crate. There is no Python lifecycle SDK yet.

```rust,no_run
use server_browser_client_sdk::{
    models::{Chivalry2Ports, ServerRegistrationRequest},
    HttpTransport, Policy, Registration, RegistrationControl,
};

# fn main() -> Result<(), Box<dyn std::error::Error>> {
let request = ServerRegistrationRequest::new(
    Chivalry2Ports::new(7777, 7778, 7779),
    "My server".into(), "Community server".into(), "map".into(), 0, 32,
);
let transport = HttpTransport::new("https://browser.example", None)?;
let mut registration = Registration::new(transport, request, Policy::default())?;
let control = RegistrationControl::default();
let worker_control = control.clone();
let worker = std::thread::spawn(move || {
    let result = registration.run(&worker_control, |event| println!("{event:?}"));
    // run cleans up on cancellation; explicitly clean up after an error.
    let cleanup = registration.stop();
    result.and(cleanup)
});
// Publish live metadata with control.publish(UpdateRegisteredServer { ... }).
// On application shutdown:
control.cancel();
worker.join().expect("registration worker panicked")?;
# Ok(())
# }
```

Applications collect game state and choose addresses/ports. The SDK serializes
registration, coalesced updates, heartbeats and deletion. It starts no hidden
threads. Use `run` on a dedicated thread or call `poll` and honor `next_delay`.
`RegistrationTransport` and monotonic `Clock` are injectable.

## Lifecycle policy

- Renew before the server lease deadline, at most every 30 seconds by default.
  Scheduling uses the difference between server timestamps and monotonic local
  time, not the client's wall clock.
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
