# Player-count and mapped-IP boundaries

- Date: 2026-11-13
- Status: implemented on branch; release unverified
- Scope: API player counts and IPv4-mapped IPv6 identity
- Repository: C2ServerBrowserBackend, `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `feature/discord-auth`; recording HEAD: `a2d2556e706b14b30f727bc3e7472f050e6181f7`; no exact tag; nearest release tag `v1.2.3` at `7b66edc60021cdbee8ffde64038b21c08f5a1d99`. Implementation and tests were uncommitted before this review.
- Source: compacted checkpoint of user and build assistant session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d8609efa0015rMuFCX747l3Kx`; earlier history is incomplete. Related [PR #18](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/18); the new implementation is not established as pushed.

## Decision and context

The local security changes extend the [registry resource bounds](2026-11-13-registry-resource-bounds.md) and [proxy trust boundary](2026-11-13-http-security-boundaries.md). The OpenAPI schema now bounds `player_count` and `max_players` independently to 0-1,024 for registration, updates and responses. The code also treats IPv4-mapped IPv6 addresses as their underlying IPv4 identity; mapped networks of prefix length at least 96 become equivalent IPv4 networks. This normalization applies to peer and forwarded addresses, request identity and IP lists.

These changes constrain accepted API values and avoid treating equivalent address representations as distinct identities at security and accounting boundaries. This rationale is inferred from the implementation and its security context; the exact trigger, choice of 1,024, and any alternatives considered are unavailable in the compacted source. They are not evidence of a broader user-approved security design.

## Consequences and evidence

Clients sending negative counts or counts above 1,024 can be rejected; the schema does not assert that current players must be at most maximum players. Mapped addresses now share IPv4 identity and mapped CIDRs may match IPv4 lists, affecting proxy trust, bans, logging and per-IP accounting. Broader IPv6 networks are not converted. Operators should reassess configured networks and clients before rollout.

The uncommitted diff includes the schema, address helpers, proxy and IP-list integration, and regression tests. The local CI log `/tmp/opencode/discord-auth-security-counts-ip-ci.log` reports 473 passing tests, mypy success across 105 files and wheel smoke success; the compatibility log reports 57 matching deterministic cases and five documented differences against `80e1fae0e635d6ae1619ab75ea87a9add50749ef`. These artifacts were inspected, not rerun, and cannot prove the current tree is identical to the tested tree. Neither a commit, remote CI, merge nor release for these changes is verified.

Reconsider the count ceiling against real server requirements and compatibility evidence, and address normalization against deployment proxy topology and IP policy. Full source deliberation and production measurements remain unknown.

## Subsequent developments (2026-11-13)

During this review another process committed the implementation as `4895a9a9e9b1f094b252cd44b76f91f3f45f0096`. Push, remote CI and release remain unverified.
