# Rust lifecycle SDK and real-server client tests

- Date: 2026-11-14
- Status: implemented on branch; merge and release pending at source response
- Scope: SDK package boundaries, registration lifecycle, client/server interoperability
- Repository: C2ServerBrowserBackend, https://github.com/Chiv2-Community/C2ServerBrowserBackend
- Recording branch: `refactor/language-sdks`; HEAD and implementation `6167869b1e371ae632a079d4efc8dad36b303bd2`; no exact tag; nearest reachable tag `v1.3.0-alpha`. Working tree clean before review.
- Source: user and build assistant session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1db264394001gXGC19tyB6znUb`; earlier history is compacted. Recorded by Annalist.

## Decision and change

The user separated generated protocol bindings (`<language>/server-browser-client`) from handwritten intended usage and business logic (`<language>/server-browser-client-sdk`). Implement the Rust lifecycle SDK now; defer the Python client SDK. This changes the [earlier Rust models/client-only scope](2026-11-14-backend-owned-language-sdks.md) and advances the [lifecycle proposal](2026-11-14-sdk-lifecycle-and-client-interop.md). The user wanted SDKs to manage registration and heartbeats rather than merely expose models and operations. The assistant's earlier suggestion to place Rust lifecycle logic inside the client crate was replaced by the user's separate-package boundary.

The backend retains contract and generator ownership. The plugin keeps game metadata, A2S discovery, address selection and worker integration; it delegates registration identity, updates, heartbeat scheduling, retries and cleanup to the SDK. Discord verification remains separate.

## Lifecycle tradeoffs

The implemented manager serializes operations, coalesces updates, schedules renewals using server-time differences and a monotonic clock, and uses bounded backoff. A missing registration (404) permits re-registration; rejected credentials halt. An ambiguous registration response halts instead of blindly retrying: the server may have created a registration whose key was lost. The protocol lacks an idempotency/recovery operation, so availability requires explicit recovery rather than risking duplicates. Cancellation cannot interrupt an in-flight request; cleanup is explicit and best-effort. Injected transports own their security policy. See [SDK documentation](../sdk/rust/server-browser-client-sdk/README.md) for exact behavior and limitations.

## Evidence and implementation

Commit `6167869b1e371ae632a079d4efc8dad36b303bd2` adds the separate Rust crate, generator text-response handling and real-server tests. The source transcript records an initial Rust Swagger `text/yaml` decoding failure and a generator-template fix rather than a hand edit of generated code. The tests exercise generated Python sync/async and Rust clients against the Python application over loopback; response validation and operation coverage are checked. The source log reports 555 Python tests, Rust lifecycle tests and verified three-crate packaging in local CI, plus 24 final targeted tests. The CI run overlapped later edits; the final targeted and Rust tests provide narrower subsequent evidence. These tests were not rerun by this review. The source response reports [backend PR #22](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/22) CI passed; remote status was not independently queried.

Plugin commit `c5fdd2cccdd7a3a805b0a3f6f2e1b9beccf4f4c6` implements delegation in [plugin PR #44](https://github.com/Chiv2-Community/UnchainedPlugin/pull/44), pinned to the backend commit. Backend merge `74e9d6ab2861109c8321156f007b3fb2596d91d9` combines this with int64 claims in [PR #21](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/21); stacked [plugin PR #43](https://github.com/Chiv2-Community/UnchainedPlugin/pull/43) uses that shared revision. The transcript records local plugin tests, loopback interop and Windows-target type checks, not execution in the game. These cross-repository results were not independently rerun. No release or registry publication is established.

## Follow-up and reconsideration

Complete stacked PR review and merge in dependency order; verify actual game integration and release artifacts separately. Reconsider ambiguous-registration handling if an authoritative idempotency or recovery contract is introduced. Python lifecycle functionality remains deferred; its timing and design are open. Earlier deliberation and current remote PR state remain unavailable or unverified.

## Subsequent developments (2026-11-14)

The plugin implementation cited above later removed its adapter crate and adopted direct SDK dependencies; the lifecycle and plugin responsibility boundaries remain. See [Plugin direct backend SDK consumption](2026-11-14-plugin-direct-sdk-consumption.md).
