# Framework-neutral server boundary proposed

- Date: 2026-11-13
- Status: proposed
- Scope: Python server contracts, FastAPI adapter and contract distribution
- Repository: C2ServerBrowserBackend; canonical remote: https://github.com/Chiv2-Community/C2ServerBrowserBackend.git
- Branch: `refactor/python-sdk-packages`; recording HEAD: `c8a2ce9a45873110202a681e11c55e2beba6b1cc`; no exact tag; nearest release tag `v1.1.2` at `80e1fae0e635d6ae1619ab75ea87a9add50749ef`.
- Source: user and build assistant, session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d61cbf71001sI26E1POyttmik`; earlier history is partly compacted. Author: Annalist. Related: [draft PR 14](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/14).

## Proposal and context

Asked about further meaningful package splits, the assistant recommended separating framework-neutral server handler interfaces and response types from a FastAPI adapter providing routers, request decoding, exception handling and HTTP rendering. The stated reason is to let alternative servers reuse interfaces without adopting FastAPI. The user asked for an assessment; the supplied conversation does not show acceptance or authorization to implement this recommendation.

This is an additional alternative to the single server-bindings distribution in [Separate Python SDK packages proposed](2026-11-13-python-sdk-packaging-proposal.md), not an approved change to that proposal. The existing generated interfaces import FastAPI `Request` and expose it in handler signatures, so the assistant correctly identified that a framework-neutral boundary needs an interface change, not merely moving files. The existing [injection implementation](2026-11-13-injection-implementation-and-interface-wiring.md) remains in effect.

## Tradeoffs and follow-up

Keeping server interfaces and FastAPI bindings together is the earlier draft's simpler arrangement; separating them may support other frameworks but adds a distribution and requires a portable request/response interface and migration strategy. The transcript does not establish a detailed design or comparison of alternatives. The assistant also recommended publishing OpenAPI as a release artifact rather than a further Python distribution, keeping registry, IP policy and authentication internal until another consumer needs them, and keeping sync and async clients in one package. These are recommendations, not user decisions.

The packaging proposal remains documentation only; no framework-neutral interfaces or new packages are implemented by it. Confirm demand from alternative server implementers, interface semantics, compatibility, versioning and release format before deciding; reconsider the split if framework independence cannot be achieved without unacceptable complexity or compatibility cost. No tests were rerun for this record. The source conversation is partly compacted, and the recommendation's detailed design and any other alternatives are unknown.
