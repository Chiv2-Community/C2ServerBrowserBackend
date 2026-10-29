# Uncommitted server listing and address formatting changes

- Date: 2026-10-29
- Status: proposed; uncommitted and not operational
- Scope: diagnostic server addresses and legacy IPv6 formatting
- Repository: C2ServerBrowserBackend; remote `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `ipv6-support`; HEAD: `532174564b4348fcf94999e32e7306022e4bb171`
- Exact HEAD tag: none; nearest tag: `v1.0.0` (seven commits before HEAD by `git describe`).
- Source: local-changes review, session `ses_e7835bca9ffepEgZb3PpLy2lem`, response `msg_187cb06200017D5KRXwxCvwepy`; reviewer: build agent. The supplied transcript omits private reasoning and may be compacted.
- Working tree: changes to API schema, response models, legacy model and API route, plus untracked `src/server_browser_backend/env.py`. These are not part of HEAD.

## Summary and context

The uncommitted work proposes moving diagnostic address exposure into `ServerResponse` and using parsed IP versions for legacy endpoint formatting. It is not evidence of an accepted API contract: the review found startup and route failures. Author intent and rationale are not available.

HEAD `532174564b4348fcf94999e32e7306022e4bb171` implements opt-in listing diagnostics with `EXPOSE_REGISTERED_IPS=1`: it otherwise omits both address keys. Commit `0e3a42d2336b5863a83bd148c6ce7078fc3273bf` introduced bracket formatting for IPv6 in legacy fields. Existing tests require omitted keys by default and bracketed IPv6 for a source-matching local client.

## Proposed behavior and alternatives

- The working tree puts nullable `ip_address` and `local_ip_address` in the response dataclass and passes an exposure flag for listings. If made operational with normal Flask dataclass serialization, disabled diagnostics would yield null fields rather than omit them. The schema marks only `ip_address` nullable. This differs from the committed omission contract; no rationale or decision to break compatibility was supplied.
- The working tree replaces the existing colon/bracket check with `ipaddress.ip_address` to determine IPv6. This rejects already-bracketed addresses, which the prior formatter passed through and registration accepts as strings. No evidence establishes whether stricter input rejection was intended.
- The prior committed implementations are the evidenced alternatives, not proven rejected decisions. The review suggested repairing callers and imports, fixing the environment helper, and preserving bracket handling or validating and normalizing registration. These are suggestions, not accepted plans.

## Evidence and consequences

The source review ran `uv run pytest -q`: collection failed in three modules because the untracked helper uses undefined `String` at import. Its mypy run also reported the helper errors, missing required `include_ip` arguments in registration and updates, and an unimported `ServerListResponse`. A separate isolated helper probe found an `UnboundLocalError` for its cache and errors on both unset and set environment values. These findings are consistent with the inspected working tree; downstream routes were not exercised end to end past the import blocker. Mypy reported additional errors, not all attributable to this change.

Until corrected and tested, the proposed implementation cannot establish working diagnostics or compatibility. Follow-up should decide whether default address keys are omitted or null, align both schema properties and tests, repair the startup and caller failures, and test bracketed and unbracketed IPv6 as well as unset and enabled diagnostics. Reconsider the proposal if compatibility requirements or validation policy are clarified. No issue, PR, author rationale, acceptance, or later fix is available in the supplied history.
