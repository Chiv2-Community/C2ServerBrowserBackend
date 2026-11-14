# SDK redirect policy and dependency security updates

- Date: 2026-11-13
- Status: implemented in the uncommitted working tree; review and publication pending
- Scope: generated Python SDK redirects and backend/mock dependency security
- Repository: C2ServerBrowserBackend, `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `feature/discord-auth`; recording HEAD: `f1ce157e171cac4928f6557e3e6acc2aac0b9bab`; no exact tag; nearest release `v1.2.3` at `7b66edc60021cdbee8ffde64038b21c08f5a1d99`.
- Source: user and build assistant, session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d85071370017fAEFJ7m71yC0r`. Earlier history is compacted and incomplete. Related [PR #18](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/18), whose reported head at the source response was `1d3a1b9be658f0d120359941d9b76a6d307cdc0f`.

## Decision and evidence

After the user requested another vulnerability search and patch, the assistant chose to disable automatic redirects on every synchronous and asynchronous SDK request, including when an injected HTTPX session enables redirects. A reported reproduction showed a borrowed redirect-following session sending a custom admin credential header to another origin. The transcript records 12 regression cases failing before the change; the current generator template, generated runtime, and tests contain the fix. This review did not rerun the reproduction. The policy also blocks same-origin redirects and HTTPS downgrades: callers receive the 3xx response and must validate a new endpoint before reconfiguring. The previously inherited session redirect setting was the observed behavior, not an evidenced deliberate alternative; other alternatives are unknown.

The assistant also updated both lockfiles for PyJWT, cryptography, certifi, urllib3, idna and Black as applicable, and raised direct minimums for PyJWT, cryptography and Black in project manifests. The source transcript reports 36 open default-branch Dependabot alerts; a script compared their reported version ranges to the revised lockfiles, and two exported-requirements pip-audit runs reported no known vulnerabilities. The audit JSON artifacts are present locally. These results concern the specific exported dependency sets and advisory data at that time; they do not prove the application or all supported environments vulnerability-free. The source response did not claim that GitHub had closed the alerts.

## Consequences, validation and follow-up

The change is a behavioral restriction for clients that relied on borrowed-session redirects. The SDK [documentation](../docs/python-packaging.md) describes the new policy; [generator template](../packages/server-browser-codegen/src/server_browser_codegen/templates/client/runtime.mustache) and generated runtime must remain aligned. Reconsider if a future use case needs redirects and a reviewed design can prevent credential forwarding and downgrades.

The local CI log reports 435 passing tests, mypy across 105 files, generated-source checks and installed-wheel smoke tests. The transcript reports successful compatibility replay and both dependency audits. This review inspected the log and artifacts but did not rerun these checks. Mock mypy's normal command failed because it inherited an unavailable Pydantic plugin; a standalone-config source check passed. Dependency updates and redirect changes were uncommitted at the source response and remain uncommitted at recording; PR #18 did not include them at that checkpoint. Verify supported Python/platform resolution, independent security review, CI, and remote PR state before release. Reassess versions as advisories change. No independent inventory of deployed clients or earlier design deliberation was available.

The earlier [HTTP security boundaries record](2026-11-13-http-security-boundaries.md) covers separate server-side hardening; this record does not supersede its decisions.
