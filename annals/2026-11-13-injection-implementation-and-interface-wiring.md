# Dependency injection implementation and interface wiring

- Date: 2026-11-13
- Status: implemented
- Scope: application composition and generated interface boundary
- Repository: C2ServerBrowserBackend; canonical remote: https://github.com/Chiv2-Community/C2ServerBrowserBackend.git
- Branch: `refactor/oas-generated-api`; recording HEAD: `1b54b5aea4e4c1271e33dc7232759b2074098503`; no exact tag; nearest release tag `v1.1.2` at `80e1fae0e635d6ae1619ab75ea87a9add50749ef`.
- Source: user and build assistant, session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d5e3f0be001xHIDSfGII2ZmH9`; earlier history is partly compacted. PR [#13](https://github.com/Chiv2-Community/C2ServerBrowserBackend/pull/13).

## Decision and change

The user requested shared dependencies be injected when services are constructed. The previously [accepted but uncommitted decision](2026-11-13-constructor-dependency-injection.md) was implemented in `1609ab2626be5f66347faed00d34c4dc683f431f`. Production `main.py` constructs one service graph, and `Application` binds injected browser and compatibility services to generated routers. Independent application graphs permit isolated tests; registry state and keys remain process-local. This does not change the synchronous-handler decision.

Follow-up `7634006ccc226a5533b1cec14e701996933bf8be` types `Application` against generated API interfaces rather than concrete implementations. The assistant identified this as a cleanup enabling interface collaborators; a test exercises both routers with mocked generated interfaces. The earlier concrete typing worked but coupled application wiring to implementations. No evidence establishes that other alternatives were separately considered.

The old record's instruction to commit the implementation is complete, not a reversal of the decision. The commits and current source verify implementation; the supplied transcript reports both commits pushed. Subsequent `1b54b5aea4e4c1271e33dc7232759b2074098503` consolidates IP-list mutation and isolates persistence fixtures while retaining credential-before-input validation; it is cleanup, not a new authorization policy.

## Evidence, consequences and follow-up

The supplied CI output for the final cleanup reports 268 tests passed, generation and typing checks, builds and IPv4/IPv6 wheel smoke; compatibility replay reports 59 exact cases and three documented differences against the baseline. These runs were not independently repeated for this record and do not establish exhaustive compatibility. Isolated graphs improve substitution and testing but require explicit composition; they do not make multiple workers share state or signing keys. Reconsider service lifetimes and persistence if multi-process deployment is required, and retain compatibility and injection tests when changing wiring.

The source conversation contains a compaction, so earlier rationale and any additional alternatives remain unknown. No independent live-client or Windows validation is established here.
