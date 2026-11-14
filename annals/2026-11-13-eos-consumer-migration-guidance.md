# Remove EOS consumer migration guidance

- Date: 2026-11-13
- Status: accepted; documentation changes uncommitted at recording
- Scope: EOS authentication retirement and consumer-facing guidance
- Repository: C2ServerBrowserBackend, `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Recording branch: `feature/discord-auth`; HEAD: `fe6aa2481800b8efa4c581a4dbf2999db8a2a37c`; no exact tag, nearest tag `v1.2.3` (`v1.2.3-3-gfe6aa24`). Foundation: `521001abf30788fbafb2c253ee96fba0669d2877`. README.md and docs/discord-auth.md had uncommitted changes before this review.
- Source: user and assistant, session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d8217cee001gQDHYVTIMN541h`; supplied checkpoint is a compacted account, not the complete transcript.

## Decision and evidence

The user requested removal of EOS consumer migration warnings, saying nothing had integrated with EOS authentication. This is attributed user testimony, not an independently verified inventory of consumers. The local documentation diff removes the migration warning and EOS retirement detail from the README and Discord authentication guide; it retains the warning that OAuth, public session APIs and game admission are not implemented. The rationale was the reported absence of integrations; no other alternatives or deliberation are available.

The earlier [foundation record](2026-11-13-discord-auth-foundation.md) advised regenerating consumers of removed EOS models. That unconditional follow-up is superseded by the user's reported absence of consumers, not disproved as a technical requirement for any consumer that might exist. The foundation's retirement of the endpoint and models remains a compatibility change. Removing documentation does not change that behavior or establish that legacy joins work. Its integration and transport-security gates remain outstanding; no evidence shows the user waived them.

## Consequences and reconsideration

The working-tree documentation no longer directs EOS consumers to migrate. If an actual consumer or deployment relying on the old exchange or removed models is discovered, reassess migration guidance and compatibility before deployment. Verify the plugin and end-to-end join path before required Discord admission. The original consumer inventory, exact discussion before the checkpoint, and any later commit or release of these documentation changes are unavailable. No tests were rerun for this documentation decision.

## Subsequent developments (2026-11-13)

The documentation changes were committed in `f38ea86` after this record. No release or independent consumer inventory is established.
