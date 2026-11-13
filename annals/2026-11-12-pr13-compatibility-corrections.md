# PR 13 compatibility corrections

- Date: 2026-11-12
- Status: implemented
- Scope: EOS token claims, PlayFab validation contract, and server expiry during updates
- Repository: C2ServerBrowserBackend; remote: `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `refactor/oas-generated-api`; recording HEAD: `4753dc42c03eb299b8fd85dd8f20fa0f0381f23e`; no exact tag; nearest tag: `v1.1.2` (`80e1fae0e635d6ae1619ab75ea87a9add50749ef`). Working tree clean before this record.
- Source: user and assistant conversation `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d30d241e001MWECxRvmstrKxU`, supplied as a compacted checkpoint. Original review exchanges and full rationale are unavailable. PR: [#13](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/13).

## Decision and evidence

Preserve acceptance of an omitted, null, or populated EOS `act` external-account claim. The baseline parser at `80e1fae0e635d6ae1619ab75ea87a9add50749ef` treats a null `act` as absent. Commit `04116daef7bc9e222b0b78641063a33780a0fe00` expresses this in the authoritative OpenAPI 3.0 contract as a nullable object with an `anyOf` reference or null-only object. The schema comment explains that nullable does not relax the referenced schema; a nullable annotation beside the reference alone was therefore insufficient. Nullability is scoped to `act`, not other claims or account fields. Signed-token tests cover all three `act` forms and retain signature and claim validation.

Document PlayFab Matchmake's HTTP 400 validation response as `StatusResponse`, not `PlayfabErrorResponse`. Commit `4753dc42c03eb299b8fd85dd8f20fa0f0381f23e` changes the contract and generated interface, not the handler, and adds contract assertions for missing or invalid `LobbyId` and an omitted body. The rationale is alignment with existing emitted validation errors rather than changing the wire behavior. This corrects the preceding branch contract, not the separate packaging or handler decisions in [Contract packaging and synchronous handlers](2026-11-12-contract-packaging-and-sync-handlers.md).

Keep `find(server_list.get_all(), ...)` in the update path rather than substitute `get()`. The checkpoint attributes the choice to preserving heartbeat expiry; `server_list.py` confirms `get_all()` processes heartbeat timeouts and `api_v1.py` uses it for updates. A direct lookup would not perform that same cleanup. The full discussion and whether other alternatives were considered are unavailable.

## Consequences and follow-up

The schema's null branch is more complex but preserves the baseline's null claim without relaxing unrelated fields. Future schema or generator changes should retain both signed-token coverage and strict validation. Consumers should expect the documented status-shaped PlayFab 400; reconsider if the actual validation response changes. Any lookup optimization must preserve expiry semantics or explicitly decide to change them.

The checkpoint reports three review passes, 256 passing tests and green CI at `4753dc42c03eb299b8fd85dd8f20fa0f0381f23e`; these results were not independently rerun or verified for this record. It reports 59 exact HTTP/state compatibility matches and three documented differences, not exhaustive equivalence. Docker, Windows and live integrations were not rerun in the final review. Commit `30dfe6528e4605db4f56bf4f431d670d55bc845b` also reuses Pydantic field annotations during decoding; its performance rationale and independent consequences are not established by the checkpoint. Earlier conversation and review findings remain incomplete.
