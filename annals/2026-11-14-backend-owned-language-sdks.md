# Backend-owned language SDKs

- Date: 2026-11-14
- Status: implemented on branch; merge and publication pending at source response
- Scope: OpenAPI SDK ownership, Python and Rust packages, plugin migration
- Repository: C2ServerBrowserBackend, https://github.com/Chiv2-Community/C2ServerBrowserBackend
- Recording branch: `refactor/language-sdks`; HEAD and implementation `0149b1a049c6d9c8101ef9eaa64ba031388787c8`; no exact tag; nearest tag `v1.3.0-alpha` at `484910715e6a9a4c34d4a36bed4d77ae420040a9`. Working tree clean before review.
- Source: user and build assistant session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1daf085be001hL03wKRVQZDxnJ`; only a compacted checkpoint of earlier conversation was available. Recorded by Annalist.

## Decision and context

The user chose backend ownership of SDK generation and artifacts under `sdk/<language>/<packages>`, using the backend OpenAPI specification as the authority. Retain all Python packages and generate Rust models and client crates only; plugin transport policy and Discord verification remain consumer code. The implementation and its consumption guidance are in [sdk/README.md](../sdk/README.md).

This advances the earlier [backend ownership proposal](https://github.com/Chiv2-Community/C2ServerBrowserBackend/blob/f8553c3ad03ccadccc1dbad5bd3e38206a05515e/annals/2026-11-14-shared-sdk-ownership-proposal.md) from proposed to implemented on this branch. That historical record is on another Git history and is absent from this worktree; it cannot receive a local correction backlink without importing that history. Its earlier statements that approval and implementation were pending describe the earlier checkpoint, not this one.

## Evidence and rationale

The earlier proposal attributed the recommendation to the assistant: keeping contract and SDK changes together avoids coordination with a separate repository. It considered a separate SDK repository if ownership or release cadence becomes independent, and discouraged a consumer repository owning dependencies shared by peers. The available checkpoint attributes the final choice to the user but does not preserve further user rationale or complete deliberation. Rust server interfaces and framework adapters are not generated; the reason for that boundary beyond the stated choice is unavailable.

Commit `0149b1a049c6d9c8101ef9eaa64ba031388787c8` moves Python packages, adds Rust generation and crates, and updates CI and release workflows. The SDK documentation states Python package names, imports, versions and dependency boundaries remain unchanged. Until registry publication is configured, Rust consumers pin an exact backend Git revision and commit their lockfile. Client configuration remains consumer-owned, including timeouts, redirects, proxies and source-IP binding. Release workflows attach artifacts but do not publish to PyPI or crates.io.

## Related implementation and consequences

[Backend PR #22](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/22) carries the SDK implementation. Plugin commit `4011166f1735837033244ca2c1a6ebb244798752` consumes a pinned backend SDK in [plugin PR #44](https://github.com/Chiv2-Community/UnchainedPlugin/pull/44); `f63b071abae47e2d527b007b3a109a9cbd66b2a8` updates the stacked Discord foundation in [plugin PR #43](https://github.com/Chiv2-Community/UnchainedPlugin/pull/43). Backend commit `8df4820dc457fd6ae714e5efe6ad4c9beb15ab1f` regenerates 64-bit ticket timestamps in stacked [backend PR #21](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/21). Local Git history verifies these commits and their branch ancestry; the checkpoint reports the PRs were unmerged at the source response. Current remote status was not checked.

The earlier [SDK/Discord split](https://github.com/Chiv2-Community/C2ServerBrowserBackend/blob/f8553c3ad03ccadccc1dbad5bd3e38206a05515e/annals/2026-11-14-sdk-and-discord-pr-split.md) and [PR replacement](https://github.com/Chiv2-Community/C2ServerBrowserBackend/blob/f8553c3ad03ccadccc1dbad5bd3e38206a05515e/annals/2026-11-14-sdk-migration-pr-replacement.md) remain applicable, but their plugin-owned generation and old commit references describe earlier states. The source checkpoint reports local tests, packaging, Docker build and interop passed, and backend CI passed; these results were not independently rerun or verified here. Required authentication remains disabled according to the checkpoint; OAuth and native admission are unfinished.

Coordinate PR merge order, pin updates and eventual registry ownership before publication. Reconsider the repository boundary if independent maintainers or release cadence justify another repository, or if contract compatibility and publication evidence require a different distribution scheme. Exact deliberations, current remote CI and PR state, and publication timing remain open.

## Subsequent developments (2026-11-14)

The models/client-only Rust package scope in Decision and context is partially superseded: a separate handwritten lifecycle SDK was added. Backend ownership and generated protocol boundaries remain. See [Rust lifecycle SDK and real-server client tests](2026-11-14-rust-lifecycle-sdk-implementation.md).
