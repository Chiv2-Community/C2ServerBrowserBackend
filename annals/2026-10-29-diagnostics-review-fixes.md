# Diagnostic listing and IPv6 review fixes

- Date: 2026-10-29
- Status: proposed; implementation uncommitted
- Scope: listing address disclosure, environment parsing, legacy IPv6 formatting
- Repository: C2ServerBrowserBackend; remote `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `ipv6-support`; recording HEAD: `12d130dc559449938ed64ae35f4d121237844bc7`; exact tag: none; nearest tag: `v1.0.0`.
- Source: user and build agent, session `ses_e7835bca9ffepEgZb3PpLy2lem`, response `msg_187cc8e78001I95ILisYGQ6LRS`. Transcript omits private reasoning and may be compacted.
- Working tree: API schema, models, route and compatibility test modified; environment helper and its tests untracked. These implementations are not committed at HEAD.

## Decision and context

After the [earlier review](2026-10-29-uncommitted-server-listing-review.md), the user requested fixes. The build agent chose to preserve omission of both address keys in the listing when diagnostics are disabled, read the environment flag without caching, and accept already-bracketed IPv6 when formatting legacy addresses. This supersedes the earlier uncommitted proposal's null-key behavior and bracket rejection, not the committed omission contract. The agent explicitly cited preservation of existing behavior; further rationale and alternatives are not recorded.

## Evidence and implementation

- The current listing route removes both keys when disabled. The helper reads the current environment and treats trimmed, case-insensitive `1`, `true`, `yes`, and `y` as enabled; other values default to false. This broadens the committed `1`-only setting. Tests cover the flag and changing it without caching.
- Legacy formatting strips surrounding brackets before IP parsing and re-brackets IPv6. The compatibility test covers bracketed and unbracketed IPv6. Invalid non-IP inputs can still fail parsing; the registration input-validation policy remains open.
- The source transcript reports `DEBUG_MODE=true uv run pytest -q`: 70 passed after the fixes; its subsequent mypy run reported 22 errors. The transcript establishes these errors remained after the changes, but does not prove all were pre-existing relative to the branch base. No tests were rerun for this record.
- The reviewed startup `String` error, broken helper, missing listing import, and missing response-constructor arguments were addressed in the source patch. The current working tree differs from that patch: `include_ip` is required again, with explicit false arguments at registration and update callers. Its present correctness beyond inspection is not established by the earlier test run.
- `ServerResponse` includes nullable fields, so the listing omission guarantee does not automatically extend to registration and update responses. The schema marks `ip_address` nullable but not the local property. Contract alignment remains follow-up work.

## Consequences and reconsideration

The source fix restores the tested listing compatibility while retaining opt-in disclosure, but exposes more accepted truthy spellings and leaves stricter IP parsing. Before committing, verify all response shapes, schema nullability, invalid inputs, and tests against the current working tree. Reconsider if disclosure, environment configuration, or accepted address formats change. No issue, PR, release, author rationale beyond the agent's stated compatibility goal, or evidence of final acceptance is available.

## Subsequent developments (2026-10-29)

The default `include_ip=False` in the source fix was superseded by the user's requirement for explicit arguments. The later test run covers that change; the earlier run described above did not. See [explicit address disclosure](2026-10-29-explicit-address-disclosure.md). Other decisions and open contract questions in this record remain applicable.

The source fix's listing key omission and route-level filtering were subsequently superseded in the supplied conversation by model-owned selection with null values; later working-tree evidence differs again. See [model-owned address selection](2026-10-29-model-owned-address-selection.md).
