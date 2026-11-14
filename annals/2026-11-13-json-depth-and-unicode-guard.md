# JSON depth and Unicode guard

- Date: 2026-11-13
- Status: implemented on branch; release unverified
- Scope: JSON request ingestion, generated FastAPI runtime, registry safety
- Repository: C2ServerBrowserBackend, `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `feature/discord-auth`; recording HEAD: `429b0686586157bfe06a83ce8986eef6c598c8cb`; no exact tag; nearest release tag `v1.2.3` at `7b66edc60021cdbee8ffde64038b21c08f5a1d99`. Implementation, contract, documentation and tests are uncommitted.
- Source: compacted checkpoint of user and build assistant session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d867eb49001TTRjzPF0q3JS2W`; earlier history is incomplete. Related [PR #18](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/18); inclusion in the PR is not verified.

## Decision and context

Extend the existing [1 MiB JSON body limit](2026-11-13-http-security-boundaries.md) with an OpenAPI-defined maximum of 64 object/array levels, counting the root, and reject strings or object keys that cannot be UTF-8 encoded. The generated FastAPI runtime validates the decoded JSON iteratively before model decoding or state changes; malformed Unicode and excessive nesting return HTTP 400. Its iterator stack bounds traversal state by nesting depth rather than container width. The generator template and generated runtime both contain the guard.

The supplied checkpoint attributes the work to reproduced registry listing failures caused by unpaired surrogates and malformed-body error rendering that could expose credentials in logs. The tests exercise rejected registration and update without registry corruption, secret-free error logging, valid escaped and unescaped Unicode, and the 64/65 depth boundary. The earlier body-size limit alone did not express these value and nesting constraints. The rationale for exactly 64 and other considered alternatives are unavailable; retaining the prior behavior is not evidence of a considered option.

## Consequences and evidence

Clients with deeper JSON or unpaired surrogates now receive HTTP 400, while tests expect valid Unicode to round-trip. The limit applies to decoded containers, not slow requests or concurrent traffic; existing proxy and concurrency precautions remain relevant. The local CI artifact reports 485 tests and the compatibility artifact reports 57 deterministic cases matching baseline `80e1fae0e635d6ae1619ab75ea87a9add50749ef` with five documented differences. The CI log also contains wheel smoke output. These artifacts were inspected, not rerun, and do not establish that the present diff is identical to the tested tree. The reported reproductions were not independently repeated.

Reconsider the depth limit if legitimate payloads require deeper nesting, and reassess Unicode and error logging defenses when parsing or serialization changes. Production traffic evidence, exact threshold rationale, full source deliberation, remote CI, commit, release and deployment are unverified. This extends the prior HTTP and [registry bounds](2026-11-13-registry-resource-bounds.md); it does not supersede them.

## Subsequent development - 2026-11-13

The implementation, contract and tests were committed in `51ea012833a0c99b8227de7af2ef686c9c639571`; the earlier uncommitted status and unverified commit refer to the original recording time. This is an implementation milestone, not a changed decision. Review source: checkpoint of session `ses_e2fd4d988ffeEfPUe73w30m5Fd` through response `msg_1d876219f001Npop7196GouSWm`. The checkpoint reports a push to PR #18, but remote inclusion and CI were not independently verified in this review.
