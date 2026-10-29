# Model-owned address selection and null serialization

- Date: 2026-10-29
- Status: accepted in source conversation; implementation then uncommitted and since changed
- Scope: server response construction and address disclosure
- Repository: C2ServerBrowserBackend; remote `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `ipv6-support`; recording HEAD: `3af1b312eae12f44585cfd7c48fa9aa665b9fbb9`; exact tag: none; nearest tag: `v1.0.0`.
- Source: user and build agent, session `ses_e7835bca9ffepEgZb3PpLy2lem`, response `msg_187cee8280014M0ap6Nkj65m0u`. The transcript omits private reasoning and may be compacted.
- Working tree: implementation, schema and tests modified or untracked; current changes are not committed at HEAD.

## Decision and context

The user directed that `ServerResponse.from_server` decide whether addresses are included in the model, rather than removing address keys in the listing route. The preceding [review fix](2026-10-29-diagnostics-review-fixes.md) had deliberately preserved omitted keys when diagnostics were disabled, and [explicit disclosure](2026-10-29-explicit-address-disclosure.md) required callers to supply the flag. The user rejected route-level filtering, not the explicit flag.

The build agent implemented model-controlled nullable values and stated the consequence: disabled address fields serialize as `null`, rather than being omitted. The schema and listing test were adjusted accordingly. This superseded the earlier omission choice for that source response, reviving the null shape initially described in the [reviewed proposal](2026-10-29-uncommitted-server-listing-review.md). The user stated the model-ownership preference; a separate rationale for the compatibility change is not recorded. Route filtering was the evidenced alternative, preserving the previous wire shape but placing the decision outside the model.

## Evidence, consequences and current state

The source patch removed the route's `pop` loop, retained explicit `include_ip`, and updated address descriptions and tests. Its test output reports `DEBUG_MODE=true uv run pytest -q`: 70 passed. That output verifies the reported run, not all clients' compatibility. The earlier claim that all 22 remaining mypy errors were pre-existing was not established against a baseline; the [fix record](2026-10-29-diagnostics-review-fixes.md) preserves that qualification.

At recording time the working tree differs materially from the source response: the model now uses a separate `ServerResponseWithIP` subclass, and the listing test again expects omitted keys when disabled. The schema also describes separate response shapes. This is evidence of a later uncommitted implementation, not evidence of when or why the plan changed or of user acceptance of that later shape. The transcript through the specified response cannot establish the later decision. No test was rerun for this record.

The null-versus-omitted difference can affect clients and API contracts. Reconcile the later working tree with its missing discussion before treating either shape as final; verify listing, registration and update responses, schema, and client compatibility. Reconsider if disclosure or serialization requirements change. No issue, PR, release, or further rationale is available in the supplied history.
