# Authentication timing and bounded cleanup corrections

- Date: 2026-11-13
- Status: implemented; authentication integration remains pending
- Scope: internal SQLite sessions and signing key rotation
- Repository: C2ServerBrowserBackend, `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `feature/discord-auth`; recording HEAD: `1879fe2f353376dd15996126ec28e836b3a7da49`; no exact tag; nearest release tag `v1.2.3`. Foundation: `521001abf30788fbafb2c253ee96fba0669d2877`; fixes: `8ebcdbbd88463266e99387d3a104bf174ee4bd19` and `1879fe2f353376dd15996126ec28e836b3a7da49`.
- Source: build assistant and independent reviewers, session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d8401ef4001zKx44NgoLxF5ha`. The preceding conversation was compacted; complete earlier history is unavailable. Working tree was clean at recording.

## Decision and evidence

Preserve the security and resource bounds of the [authentication foundation](2026-11-13-discord-auth-foundation.md), but correct its timing and cleanup implementation. Independent review reported reproducible boundary failures; the changes and regression tests are present in the two fix commits. These are corrections to implementation, not a reversal of the foundation's intended expiry, overlap, or storage policies.

- Sample session time after acquiring the SQLite transaction lock. Previously a request waiting across absolute expiry could authenticate against a stale timestamp.
- Count only live sessions for live-session quotas. Bounded cleanup can leave expired rows behind; previously a quota rejection rolled cleanup back, so repeated requests could fail indefinitely even with no live sessions. A savepoint now preserves bounded cleanup on capacity and too-soon rejections while rolling back request changes; physical credential and database limits still apply.
- Coordinate issuance with publication using a shared issuer lock and exclusive rotation lock; refresh the key snapshot and sample issuance time under the lock. RSA generation happens outside exclusive publication, and writers reread under lock. JWKS readers remain lock-free. The provisioned lock file must remain readable by the backend.

The first rotation fix moved the retirement timestamp after RSA generation. The next review reproduced another failure: slow file publication could still let an old-key ticket outlive its published verification key. Merely moving the timestamp past generation was therefore insufficient; synchronized cutover was chosen to prevent issuance across the retirement boundary. This adds lock coordination and a Linux filesystem-lock dependency in exchange for protecting the intended overlap. The earlier implementation did not establish that the intended overlap held under delayed publication.

## Validation and limits

The supplied transcript reports deterministic lock-wait, quota, delayed-publication and cleanup regressions, 408 passing tests, mypy across 104 files, generated-code checks and full local CI; an independent final review reported no actionable issues. A subsequent independent cleanup review reported 408 tests and no actionable simplification, but did not rerun package/wheel CI. The commits and regression test files were verified in the repository; these test runs were not independently rerun for this annal. Clean review is not proof of absence of defects.

OAuth, public session and ticket operations, and plugin admission remain unimplemented. Reconsider the lock design if deployment changes filesystem or host topology, or evidence shows issuance availability or verification overlap cannot be maintained. Investigate any new expiry, publication, storage exhaustion or cleanup failure at the actual production boundary. The full historical deliberation and other considered alternatives are unavailable.
