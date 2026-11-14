# SDK lifecycle and client interop direction

- Date: 2026-11-14
- Status: proposed; client interop tests and text-response fix uncommitted
- Scope: registration and heartbeat lifecycle, generated-client integration testing
- Repository: C2ServerBrowserBackend, https://github.com/Chiv2-Community/C2ServerBrowserBackend
- Recording branch: `refactor/language-sdks`; HEAD `62f8cd026ac24a8e55ccd79e441b9f24146deecb`; no exact tag; nearest reachable tag `v1.3.0-alpha-6`. Working tree contains uncommitted SDK generator and client changes and untracked tests.
- Source: user and assistant session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1db073eb4001tVWGHCgT65b2ix`; supplied checkpoint summarizes earlier conversation and is not a complete transcript. Recorded by Annalist.

## Direction and context

The user requested generated-client end-to-end tests against the actual Python server and a richer SDK that manages registration and heartbeats, beyond generated bindings. This extends, but does not replace, the [backend-owned SDK decision](2026-11-14-backend-owned-language-sdks.md). Engine adapters and Discord verification remain plugin responsibilities; required authentication remains gated on integration, according to the checkpoint.

The assistant proposed Python registration managers and Rust lifecycle code, with bounded retries, cancellation, non-overlapping requests and credential secrecy. These are proposals, not approved semantics or implemented lifecycle features. The checkpoint does not preserve detailed rationale, design discussions, or genuinely considered alternatives; none are inferred here.

## Evidence and implementation state

The worktree contains untracked Python and Rust client end-to-end tests and uncommitted Rust generator, generated client and template changes. The generator changes identify non-JSON string response media types for raw-text handling. The checkpoint reports that tests exposed Rust Swagger `text/yaml` decoding failure and that an E2E run passed after a template fix, but subsequent test edits were interrupted. This review did not run the tests or independently verify that failure or pass; current validation remains outstanding. The uncommitted changes are not pinned to a Git commit.

The checkpoint also identifies ambiguous registration timeouts as a possible need for an OpenAPI-defined idempotency mechanism. Retry safety, API shape, ownership of lifecycle state, and precise cancellation and shutdown behavior remain open. Do not assume a timeout means registration failed or that automatic retries are safe without contract evidence.

## Consequences and reconsideration

Validate final E2E changes against local services and review generated text decoding before treating them as complete. Agree lifecycle semantics and integration boundaries before implementation; retain secret-safe errors and logging. Reconsider retry design when registration outcomes, duplicate behavior and any idempotency contract are established. No release, PR state change, implementation authorization or lifecycle approval can be established from the supplied checkpoint.
