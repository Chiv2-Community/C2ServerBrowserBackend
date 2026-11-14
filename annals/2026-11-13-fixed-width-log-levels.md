# Fixed-width console log levels

- Date: 2026-11-13
- Status: implemented
- Scope: application and Uvicorn console log formatting
- Repository: C2ServerBrowserBackend, `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Recording branch: `feature/discord-auth`; HEAD: `006fbf075a65c0a249f39ba4a0adcaeac2cb0a95`; no exact tag; nearest tag `v1.2.3` at `7b66edc60021cdbee8ffde64038b21c08f5a1d99`.
- Implementation: `3e3a9a199ad6eb91a9a68882acb3439d90418945`; merged in [PR #17](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/17) at `7b66edc60021cdbee8ffde64038b21c08f5a1d99`.
- Source: supplied compacted checkpoint of user and assistant session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d820132c001KU0k9OpmUcTLG3`; earlier details are unavailable. Unrelated README and Discord documentation edits were uncommitted at recording and do not establish a change to this decision.

## Decision and evidence

The [earlier unified logging decision](2026-11-13-unified-request-log-format.md) used a minimum five-character level field without truncation. Version `v1.2.3` supersedes that field's width policy: the level is right-padded or truncated to exactly five characters. `WARNING` becomes `WARNI` and `CRITICAL` becomes `CRITI`; the IP field remains minimum width 15 without truncation.

The implementation changes `%(levelname)-5s` to `%(levelname)-5.5s`, updates the README and adds test expectations for truncated names. The merge commit and local tag establish that the change is in the tagged Git tree; the checkpoint reports publication, but a hosted release and deployment were not independently checked. Tests were not rerun for this review.

## Rationale and consequences

Fixed width aligns the level field, but loses the suffix of long level names. The earlier untruncated format preserved complete names but allowed the column to expand. The historical reason for choosing truncation, and whether other alternatives were considered, are unavailable; alignment is an observable effect, not an attributed motive.

Log consumers and operators must recognize truncated names. Reconsider if parsers require full severity names or additional names become ambiguous. The rest of the earlier logging decision, including request attribution and proxy-policy risks, remains in effect. Verify deployment and downstream parser compatibility separately.
