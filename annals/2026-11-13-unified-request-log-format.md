# Unified console logs and request attribution

- Date: 2026-11-13
- Status: implemented on PR branch; not merged or released at source response
- Scope: console logging, request context, Uvicorn
- Repository: C2ServerBrowserBackend, https://github.com/Chiv2-Community/C2ServerBrowserBackend
- Recording branch: `fix/unified-log-format`; HEAD: `6ef923e16e542939f292a4bd6d9d800ff58936c0`; no exact tag; nearest tag `v1.2.1`.
- Base and release: `d6f66fd15831023cff08b7d442848319afcb0a28` (`v1.2.1`).
- Source: user and build assistant, session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d7eb1dd2001X2fundzTODw0KU`. Earlier history was compacted and is incomplete.
- Related: [PR #16](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/16); [earlier proposal on another branch](https://github.com/Chiv2-Community/C2ServerBrowserBackend/blob/1b7cbd0/annals/2026-11-13-successful-heartbeats-and-log-formats.md).

## Decision and context

The user requested one console format after observing that v1.2.1 application and Uvicorn logs used different handlers and formats. The accepted format is `DATE | LEVEL | REQUESTOR IP | NS - message`; levels have minimum width five and IPs minimum width 15, right-padded without truncating long values. A prior assistant proposal omitted the requestor IP; the user subsequently added it. The earlier proposal on the other branch is therefore partially superseded, not refuted. That branch's annals are absent from this worktree; its record could not be backlinked without changing another branch.

## Choice and evidence

Commit `c328a67219384bfda3aea6659199516e4d1602f7` reuses the existing forwarded-header policy and request scope through a context variable, including synchronous workers, and formats application and Uvicorn console handlers while retaining their controls. Invalid or absent request IPs render as `-`. The user wanted operational consistency; preserving separate Uvicorn levels and existing proxy behavior was an implementation constraint. Keeping the mixed format was the prior state, not a documented rejected alternative; no other alternatives are evidenced.

Review of real Uvicorn requests exposed loss of request attribution after context reset. Commit `e709636ed4daaa385998bf9a849f264c859cb5b3` attaches normalized IP metadata to escaping exceptions. A second review found cancellation and fallback access records also lost attribution; `d2b3314368c5eca6aae4c702705dc9a60e7fe96e` handles escaping `BaseException` and extracts the client address from standard Uvicorn access records. Context is still reset and exceptions re-raised. The fallback depends on Uvicorn's standard access record shape.

The independent review in the supplied transcript reported no actionable issues at `d2b3314`. The user then requested test cleanup; `6ef923e16e542939f292a4bd6d9d800ff58936c0` changes only tests, sharing helpers and replacing synthetic ASGI requests with HTTPX. The source transcript reports 351 tests, full local CI and exact-head GitHub CI passing, and a further independent full review without actionable findings. The local commit and test changes were verified; tests and remote CI were not rerun during this annals review.

## Consequences and reconsideration

Console logs expose requester addresses under the existing trusted-proxy policy; protect log access. Access messages may include URLs and tracebacks may include exception details. Review compatibility if proxy trust, Uvicorn access-record shape, logging sinks, cancellation behavior or privacy requirements change. Confirm deployed behavior after merge and release; neither is established by the source response. Live Graylog delivery and earlier compacted decision history remain unverified.
