# server-browser-auth-sdk

Offline verification of backend-issued join tickets using generated claims and
JWKS models. No game hooks, HTTP client, OAuth flow, or key discovery.

```rust,no_run
use server_browser_auth_sdk::TicketVerifier;

# fn verify(jwks: &[u8], ticket: &str, now: u64) -> Result<(), Box<dyn std::error::Error>> {
let mut verifier = TicketVerifier::new(
    "https://browser.example",
    "00000000-0000-4000-8000-000000000001",
    jwks,
    1024,
)?;
let identity = verifier.verify_and_consume(ticket, now)?;
# Ok(())
# }
```

- Own one verifier per live registration; serialize consumption with admission.
- Supply trusted Unix time and externally trusted JWKS snapshots.
- `replace_keys` preserves replay history; failed replacement preserves keys.
- Verification enforces RS256, ticket type, issuer, registration audience,
  canonical IDs, required claims, a 60-second maximum lifetime and 30-second skew.
- Token/JWKS sizes, key counts and replay history are bounded. Full replay
  capacity rejects admission without evicting live entries.
- Unknown keys never trigger network requests. Header-supplied keys/URLs are rejected.
- Callers own identity/connection binding, confidential ticket transport,
  key-refresh policy and native admission gates.

Run portable tests with `cargo test --locked --manifest-path sdk/rust/Cargo.toml
-p server-browser-auth-sdk`. The ignored `backend_signing` test requires Docker
and checks compatibility with the published backend image:

```sh
cargo test --locked --manifest-path sdk/rust/Cargo.toml \
  -p server-browser-auth-sdk --test backend_signing -- --ignored
```
