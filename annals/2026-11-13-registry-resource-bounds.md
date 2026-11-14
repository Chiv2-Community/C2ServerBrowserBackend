# Bound registry state and metadata

- Date: 2026-11-13
- Status: implemented on PR branch; release pending
- Scope: server registration, metadata and MOTD selector resource limits
- Repository: C2ServerBrowserBackend, `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `feature/discord-auth`; recording HEAD and implementation: `ca29f364f82a93fac05c659d5a4c25ea234ec328`; no exact tag; nearest release tag `v1.2.3` at `7b66edc60021cdbee8ffde64038b21c08f5a1d99`. Working tree clean before this review.
- Source: user and build assistant, session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d85859900018DVXaLkWLqR9W7`; earlier conversation is compacted and incomplete. Related [PR #18](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/18).

## Decision and context

After the user requested continued vulnerability fixes, the assistant bounded unauthenticated registry admission and retained metadata. The prior registry had no registration capacity bound; the transcript reports 2,000 same-IP registrations accepted by the original implementation. A 1 MiB request limit alone, introduced in the [HTTP security boundaries record](2026-11-13-http-security-boundaries.md), does not bound the number or total size of retained records.

The implemented choice uses atomic per-process quotas, defaulting to 1,024 registrations globally and 16 per source IP, configurable via `MAX_REGISTERED_SERVERS` and `MAX_REGISTERED_SERVERS_PER_IP`. Registration reclaims expired entries, then returns HTTP 429 on capacity without evicting live registrations. Hosts behind one public IP share a quota. The OpenAPI contract caps names and maps at 256 characters, descriptions at 4,096, mod lists at 64, and mod name/organization/version at 128/128/64 characters. These also constrain updates. Retaining the unbounded registry was the previous behavior, not a documented considered alternative; the reason for the precise numeric defaults and other options is unavailable.

The same commit makes MOTD language selectors longer than 32 characters or non-alphanumeric fall back to English. The transcript reports oversized selectors previously caused filesystem errors containing attacker-controlled text in logs; fallback preserves a usable response instead of passing oversized filenames to the filesystem.

## Consequences and evidence

The commit changes the API and operational limits; legitimate shared-IP hosts or unusually large metadata may be rejected. Quotas bound retained state, not request rate, CPU, slow clients or aggregate connections. Proxy rate and concurrency controls remain necessary, and the registry is process-local: use one worker until its ownership model changes. Correct source-IP accounting depends on the configured trusted-proxy boundary.

The commit contains implementation, OpenAPI changes and regression tests for concurrent quotas, expiry reclamation, metadata bounds and MOTD fallback. The local CI artifact reports 454 tests, mypy across 105 files, generated-source checks and installed-wheel smoke checks; the transcript reports compatibility replay success. These runs were not repeated during this review. The source transcript reports the commit pushed to PR #18 and remote CI queued; current remote status and deployment were not independently checked. The local Git tree verifies the commit, not a merge or release.

Reconsider defaults against production host density, shared-IP deployments and actual metadata; reassess limits or registry ownership if topology changes. Original traffic measurements, a complete security assessment and other deliberations are unavailable.

## Related developments

The earlier [SDK redirect and dependency security record](2026-11-13-sdk-redirects-dependency-security.md) described changes as uncommitted at its checkpoint. They were subsequently committed in `54a77cd7d3caa6fc4a59773772a69222ca410444` and, according to the source transcript, pushed to PR #18. This changes implementation status, not the decision or the scope of the earlier audit.
