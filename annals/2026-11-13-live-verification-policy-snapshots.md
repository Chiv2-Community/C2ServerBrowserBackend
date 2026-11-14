# Live verification and atomic IP policy snapshots

- Date: 2026-11-13
- Status: implemented on branch; release unverified
- Scope: verified and banned IP policy, listings and persistence
- Repository: C2ServerBrowserBackend, `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `feature/discord-auth`; recording HEAD: `0b98dc7a1979ca06f9fec6cf0a9de89e29546858`; no exact tag; nearest release tag `v1.2.3` at `7b66edc60021cdbee8ffde64038b21c08f5a1d99`. The implementation, documentation and tests described here are uncommitted.
- Source: compacted checkpoint of user and build assistant session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d872203f001LKrgdi0Unf78FJ`; earlier conversation is incomplete. Related [PR #18](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/18); inclusion of these changes is unverified.

## Decision and context

The local changes derive verified/official status from current verified-IP policy and the observed registered server IP, including for existing registrations. API listings, updates and heartbeats, and TBIO listings apply the current policy rather than relying solely on registration-time status. This permits grants and revocations to affect live listings. The policy tests exercise revocation during registration, grant and revocation, and distinguish the server IP from the viewer and local addresses. A registration response is still based on the check performed during registration; no global transactional snapshot across a listing is claimed.

For IP lists, writers within one application instance serialize changes and publish immutable in-memory snapshots after writing and atomically replacing the complete file. A private temporary file, file flush and POSIX directory flush support persistence. A pre-replacement failure leaves the old snapshot active; if directory flushing fails after replacement, the new snapshot is active but crash durability is uncertain. Callers should read back before retrying. Reads return detached sets. These choices address stale verification grants, lost concurrent changes and unsafe persistence, as evidenced by the implementation and regression tests; exact conversation rationale and other genuinely considered alternatives are unavailable. The previous registration-time flag and earlier persistence behavior are observed baselines, not established rejected proposals.

## Consequences and evidence

Policy changes can alter official flags without re-registration. Atomic replacement and immutable snapshots do not coordinate independent writers or multiple backend workers; the [operator documentation](../README.md) requires a private policy directory and a single writer instance. The tests in [policy security](../src/test/server_browser_backend/test_policy_security.py) cover concurrent adds, pre- and post-replacement failures, snapshot isolation and temporary-file symlink handling. This extends, rather than supersedes, the [mapped-IP identity boundaries](2026-11-13-player-count-and-mapped-ip-boundaries.md).

The local CI artifact `/tmp/opencode/discord-auth-security-policy-ci.log` reports 500 passing tests, mypy success across 107 files and installed-wheel smoke success. The compatibility artifact reports 57 deterministic cases matching baseline `80e1fae0e635d6ae1619ab75ea87a9add50749ef` and five documented differences. These logs were inspected, not rerun; they do not prove the current working tree is identical to the tested tree. Remote CI, commit, release and deployment are unverified.

Reconsider persistence and locking if multiple processes, external policy editors, shared filesystems or stronger crash-durability guarantees become requirements. Reconsider response consistency if clients require a single policy snapshot across an entire listing or registration operation. Original deliberation, production topology and observed production failures remain unknown.

## Subsequent development - 2026-11-13

The implementation, documentation and tests were committed in `51ea012833a0c99b8227de7af2ef686c9c639571`; the earlier uncommitted status and unverified commit refer to the original recording time. This is an implementation milestone, not a changed decision. Review source: checkpoint of session `ses_e2fd4d988ffeEfPUe73w30m5Fd` through response `msg_1d876219f001Npop7196GouSWm`. The checkpoint reports a push to PR #18, but remote inclusion and CI were not independently verified in this review.
