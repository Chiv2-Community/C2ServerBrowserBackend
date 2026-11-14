# Total JSON upload deadline

- Date: 2026-11-13
- Status: implemented locally; uncommitted
- Scope: JSON request ingestion, generated FastAPI runtime, HTTP timeout handling
- Repository: C2ServerBrowserBackend, `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `feature/discord-auth`; recording HEAD: `866990d3b28058d5f8a0193f8af207c90d75b115`; no exact tag; nearest release tag `v1.2.3` at `7b66edc60021cdbee8ffde64038b21c08f5a1d99`.
- Source: compacted checkpoint of user and build assistant session `ses_e2fd4d988ffeEfPUe73w30m5Fd` through response `msg_1d87dfa83001icJT2nEa7ZreK1`; earlier conversation is incomplete. Related [PR #18](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/18). Upload-deadline implementation and tests are uncommitted at recording; other implementation files also have pre-existing modifications.

## Decision and context

Bound the total time spent streaming a JSON request body to 10 seconds, as specified by `x-json-body-timeout-seconds` in the OpenAPI contract. The generated FastAPI runtime and its generator template use AnyIO `fail_after` around the whole stream, not a fresh timeout per chunk. This addresses stalled or trickling uploads, which the existing [body-size limit](2026-11-13-http-security-boundaries.md) and [depth and Unicode guards](2026-11-13-json-depth-and-unicode-guard.md) do not bound. These decisions are extended, not superseded.

Timeouts return HTTP 408 with `request_timeout`; HTTP/1.0 and HTTP/1.1 responses request connection closure. A client disconnect maps to malformed/missing JSON, while external cancellation propagates. Regression tests cover stalled and trickling streams with and without known length, a normal chunked request, disconnect, cancellation, and absence of credential leakage in logs.

The checkpoint attributes the choice to limiting slow uploads; the working diff confirms the implementation. A size cap alone remains necessary but does not prevent indefinitely slow delivery. No evidence establishes a deliberated alternative deadline or the reason for exactly 10 seconds.

## Consequences and validation

Legitimate slow uploads can now fail with 408; clients and proxies must tolerate the deadline and HTTP/1.x connection closure. The limit is per body read, not an aggregate concurrency limit, and does not replace proxy protections. Reconsider the threshold if observed legitimate uploads exceed it or the ingestion architecture changes.

The source response reports 507 passing tests, full local CI, compatibility replay, and a real Uvicorn timeout smoke test. The available CI log reports 507 passing tests, current generation, mypy success across 107 files, and wheel smoke output; the compatibility log reports 57 deterministic cases matching baseline `80e1fae0e635d6ae1619ab75ea87a9add50749ef` with five documented differences. Logs were inspected, not rerun; their exact tree identity and the reported real-server smoke were not independently verified. Earlier source history, production traffic data, remote CI, release and deployment remain unverified. Remote branch lookup failed during this review.
