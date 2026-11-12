# Discord identity and host-controlled admission plan

- Date: 2026-11-12
- Status: proposed
- Scope: backend, UnchainedPlugin, and UnchainedLauncher authentication and authorization
- Repository: C2ServerBrowserBackend, `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Recording branch: `refactor/oas-generated-api`; HEAD: `80e1fae0e635d6ae1619ab75ea87a9add50749ef` (exact tag `v1.1.2`). The backend migration is uncommitted; see [OpenAPI prerequisite](2026-11-12-openapi-generated-boundary.md).
- Source: session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, response `msg_1d09929e400103OtJNCqBB9lxe`; earlier history is available only as a compaction summary. The summary attributes requirements to the user and describes issue publication; original discussions and exact decision dates are unavailable.

## Plan and rationale

The planned design centralizes Discord identity at `servers.polehammer.net` while leaving authorization to each game host and its own Discord bot. This separates identity from host policy. Authentication has disabled and required modes, not an optional mode. The game would initiate browser login and pass short-lived, asymmetrically signed join JWTs; hosts would validate them against trusted JWKS and bind verified Discord identity to the player session separately from platform identifiers.

Host policies are to cover guild membership, required and blocked roles, account age, verification checks, and Discord-ID bans. The summary states that Discord tokens are discarded after identification; stateful Unchained sessions instead use rotating opaque refresh credentials, stored as hashes with bounded history for reuse detection. Account, IP, global, quota, expiry, concurrency and rotation limits are planned to bound storage and abuse. Signing keys need persistence across restarts and workers and overlapping rotation.

The launcher must persist and configure host policies and enable authentication without requiring a Discord delivery channel. Native game UI and join feasibility comes first; an UnchainedMods-internal issue is deferred unless a concrete gap is demonstrated. Launcher integration is a rollout prerequisite. The summary reports that the user removed an email-verification caveat; the exact original wording is unavailable.

## Evidence, alternatives and status

The source summary reports coordinated issues: [plugin parent #33](https://github.com/Chiv2-Community/UnchainedPlugin/issues/33), [feasibility #34](https://github.com/Chiv2-Community/UnchainedPlugin/issues/34), backend [OpenAPI #10](https://github.com/Chiv2-Community/C2ServerBrowserBackend/issues/10), [signing #11](https://github.com/Chiv2-Community/C2ServerBrowserBackend/issues/11), [OAuth #12](https://github.com/Chiv2-Community/C2ServerBrowserBackend/issues/12), plugin [client #35](https://github.com/Chiv2-Community/UnchainedPlugin/issues/35), [validation #36](https://github.com/Chiv2-Community/UnchainedPlugin/issues/36), [policy #37](https://github.com/Chiv2-Community/UnchainedPlugin/issues/37), [rollout #38](https://github.com/Chiv2-Community/UnchainedPlugin/issues/38), and [launcher #182](https://github.com/Chiv2-Community/UnchainedLauncher/issues/182). This review independently confirmed that backend #10 and plugin #33 exist and are open; other issue contents and dependency relationships were not independently checked.

Optional authentication was explicitly excluded in the summary. Native-only work is preferred over prematurely involving UnchainedMods-internal; no evidence establishes other rejected designs or their rationale. This is an issue plan, not evidence that Discord authentication was implemented or deployed. Backend OAS migration is a prerequisite; plugin feasibility must precede protocol finalization.

## Risks and follow-up

Validate the actual Discord flow and OIDC support, native UI and credential transport, connection binding, refresh retry and concurrency semantics, signing-key rotation, revocation, quotas, and integration across all three products. A join JWT may remain valid until expiry after session revocation. Coordinate launcher work with [PR #150](https://github.com/Chiv2-Community/UnchainedLauncher/pull/150) and plugin integration with [issue #5](https://github.com/Chiv2-Community/UnchainedPlugin/issues/5), as reported in the summary. Reconsider the native-only approach if feasibility demonstrates a concrete gap. Exact approval history and full issue bodies remain unverified here.
