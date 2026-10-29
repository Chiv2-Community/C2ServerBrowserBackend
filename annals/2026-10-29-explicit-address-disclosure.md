# Explicit address disclosure at response construction

- Date: 2026-10-29
- Status: accepted; implementation uncommitted
- Scope: `ServerResponse.from_server` address disclosure argument
- Repository: C2ServerBrowserBackend; remote `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `ipv6-support`; recording HEAD: `d41fa3bc5297f541149ead25d25640426acf2d6a`; exact tag: none; nearest tag: `v1.0.0`.
- Source: user and build agent, session `ses_e7835bca9ffepEgZb3PpLy2lem`, response `msg_187cdbf33001GNYtj83L9P045B`. The supplied transcript omits private reasoning and may be compacted.
- Working tree: implementation and tests modified or untracked; not committed at recording HEAD.

## Decision and context

The user requested removing the `include_ip=False` default introduced in the [review fixes](2026-10-29-diagnostics-review-fixes.md): callers should explicitly pass true or false. This replaces the build agent's earlier default-argument fix for broken constructor callers. The stated rationale is explicitness; further rationale is not recorded. The earlier default was a working alternative, not evidence of a settled long-term policy.

## Evidence and consequences

The current model requires `include_ip`; registration and update/heartbeat pass `False`, while the listing passes the diagnostics flag. The listing still removes address keys when diagnostics are disabled. Other response types serialize nullable address fields, so this does not establish that those keys are omitted everywhere. Explicit arguments make future callers choose a disclosure policy, but require call-site updates. The source transcript reports 70 passing tests after the change; an independent `DEBUG_MODE=true uv run pytest -q` also passed 70 tests during this review.

The earlier record's uncertainty about test coverage of the current explicit-argument change is resolved by the later run, not retroactively by the earlier run. Mypy had 22 remaining errors in the previous transcript; this review did not rerun it or establish their baseline. Implementation is uncommitted; no issue, PR, release, or further design discussion is available.

## Reconsideration and follow-up

Reconsider if response disclosure or compatibility requirements change. Before release, reconcile registration/update response shapes and schema nullability, and address remaining type-checking and invalid-address questions identified in the earlier review. The supplied session may not contain all historical context.

## Subsequent developments (2026-10-29)

The claim that the listing removes disabled address keys describes the earlier implementation; it was superseded in the supplied conversation by model-owned selection and null serialization. The explicit-argument decision remains. See [model-owned address selection](2026-10-29-model-owned-address-selection.md) for subsequent working-tree uncertainty.
