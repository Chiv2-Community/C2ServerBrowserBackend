# Separate Python SDK packages proposed

- Date: 2026-11-13
- Status: proposed
- Scope: reusable Python models, client and server distributions
- Repository: C2ServerBrowserBackend; canonical remote: https://github.com/Chiv2-Community/C2ServerBrowserBackend.git
- Branch: `refactor/python-sdk-packages`; recording HEAD: `73b94a426fd756eca44d706a8d56bdd8cfc27f60`; no exact tag; nearest release tag `v1.1.2` at `80e1fae0e635d6ae1619ab75ea87a9add50749ef`.
- Source: user and build assistant, session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d61b3a4c001HT7S0BaQQzJLZ8`; earlier history is partly compacted. Authoring agent: Annalist.
- Artifacts: [draft PR 14](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/14), [proposal](../docs/python-packaging.md), [merged PR 13](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/13).

## Context and decision

The user requested merging PR 13 and a separate packaging PR for Python models, client and server packages to ease alternative implementations and integrations. PR 13 merged as `68f71c58aec12ea0cadbb9348afbf0dd9f97e2ec`. Its existing `server-browser-api` distribution combines models, validation and FastAPI bindings and has no generated HTTP client. The user request establishes the goal, not approval of the detailed design.

In `73b94a426fd756eca44d706a8d56bdd8cfc27f60` the assistant proposed three independently installable generated distributions: shared models, a typed HTTP client, and reusable FastAPI server interfaces and bindings; the concrete backend would remain a fourth distribution. Client and server would depend on the same model implementation, without models or client requiring FastAPI. OpenAPI remains authoritative; existing synchronous server execution and explicit service injection remain unchanged. This is a proposed extension to [Contract packaging and synchronous handlers](2026-11-12-contract-packaging-and-sync-handlers.md), not a reversal of its implemented build-time contract packaging.

## Rationale, alternatives and consequences

The requested separation supports consumers that need only models or a client and alternative servers without installing the concrete backend. The current combined package is simpler but brings FastAPI to model-only users and lacks a generated client. The proposal introduces more distributions, dependency and version coordination, migration concerns, and release verification. The conversation does not establish a broader comparison or rejection of other designs.

The proposal calls for reproducible generation, a shared contract, independently rebuildable sdists, isolated dependency tests, typed downstream usage and client/server round trips preserving omitted versus null and IPv6 serialization. These are proposed obligations, not completed results. It also proposes no implicit mutation retries and borrowed transport ownership safeguards.

## Status and follow-up

PR 14 was opened as a draft design review; the commit changes documentation only, not distributions or imports. The source transcript shows `git diff --check` passed and says runtime tests were not rerun for that documentation change. The preceding PR 13 transcript reports 276 tests and compatibility replay with 59 exact matches and three documented differences; this review did not rerun them.

Names and compatibility for `server-browser-api`, client transport and sync/async interface, version constraints, publication channel and package-name ownership remain open. Review and approve these before implementation; reconsider the split if isolated installation, generation or compatibility requirements cannot be met. Exact earlier rationale and alternatives are unavailable due to compaction.
