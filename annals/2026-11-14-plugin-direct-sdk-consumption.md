# Plugin direct backend SDK consumption

- Date: 2026-11-14
- Status: implemented on plugin branches; merge and release unverified
- Scope: UnchainedPlugin SDK dependencies, HTTP configuration and portable tests
- Repository: C2ServerBrowserBackend, https://github.com/Chiv2-Community/C2ServerBrowserBackend
- Recording branch: `refactor/language-sdks`; HEAD `52f3da7ffe49aaa6c5c7fc18fbc1481d146ba7e9`; no exact tag; nearest reachable tag `v1.3.0-alpha`. Working tree clean before review.
- Source: supplied compacted conversation checkpoint through response `msg_1db2f0d04001a03L1DfZijuWC0`; source session ID not included in the checkpoint. Recorded by Annalist. Earlier conversation is incomplete.

## Decision and context

The checkpoint reports that the user approved removing the plugin's `crates/unchained-backend` adapter in favor of direct dependencies on the backend-generated client and handwritten lifecycle SDK. Plugin-specific HTTP user-agent configuration stays in `src/backend.rs`. A test-only package provides portable transport checks without becoming a runtime adapter. This follows the [Rust lifecycle SDK implementation](2026-11-14-rust-lifecycle-sdk-implementation.md) and preserves the [backend SDK ownership boundary](2026-11-14-backend-owned-language-sdks.md); it does not reverse either decision.

## Evidence and alternatives

Plugin commit [`df0308b90e0768d3629a101ea6f9b5a190cfd00c`](https://github.com/Chiv2-Community/UnchainedPlugin/commit/df0308b90e0768d3629a101ea6f9b5a190cfd00c) deletes the wrapper crate, adds direct workspace dependencies pinned to backend `6167869b1e371ae632a079d4efc8dad36b303bd2`, and moves the plugin's user-agent configuration to `src/backend.rs`. Its `tests/portable` package has no library or runtime consumers and imports the plugin configuration for checks. CI invokes its transport tests. Plugin merge [`e598dd93e70603c613fa97bee9bf8f36b8a56eac`](https://github.com/Chiv2-Community/UnchainedPlugin/commit/e598dd93e70603c613fa97bee9bf8f36b8a56eac) includes that commit on the stacked Discord branch. Local remote-tracking refs contain the respective commits; current server and PR state were not queried.

The previous wrapper was a genuine alternative: it provided a separate consumer-side crate and reexports. The committed plugin documentation states no adapter or reexport layer is needed; the checkpoint does not preserve further rationale or deliberation. Direct consumption removes that layer but keeps plugin-specific HTTP configuration and portable test infrastructure in the plugin. Lifecycle behavior remains backend-owned, while game metadata, address selection and worker integration remain plugin responsibilities.

## Validation and follow-up

The checkpoint reports portable tests, local backend interoperability and Windows-target checks passed. This review verified the committed test and CI configuration but did not rerun tests or independently verify those results. The Windows check does not run the game; actual game integration remains unverified. [Plugin PR #44](https://github.com/Chiv2-Community/UnchainedPlugin/pull/44) and stacked [PR #43](https://github.com/Chiv2-Community/UnchainedPlugin/pull/43) were reported pushed, not independently checked for current merge or CI status.

Reconsider a separate adapter if future consumer-specific policy or additional consumers justify a runtime boundary. Verify game integration and PR/SDK release order before treating the migration as deployed. Full discussion, detailed user rationale, source session ID and current remote status remain unavailable.
