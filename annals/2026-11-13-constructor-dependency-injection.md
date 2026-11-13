# Constructor-based dependency injection

- Date: 2026-11-13
- Status: accepted; implementation uncommitted
- Scope: application composition, shared services, and test isolation
- Repository: C2ServerBrowserBackend; remote: `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `refactor/oas-generated-api`; recording HEAD: `bb4d2b7703b694131199c9b465e44f7fcccc9e94`; no exact tag; nearest tag: `v1.1.2` (`80e1fae0e635d6ae1619ab75ea87a9add50749ef`). The implementation and related tests were uncommitted at recording; HEAD alone does not contain them.
- Source: user and assistant conversation `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d5d54bab001pHID3aycu0D4bK`, supplied as a partly compacted checkpoint. Exact request wording and earlier discussion are unavailable.

## Decision and context

The checkpoint attributes the request for constructor-based injection of shared services to the user. The assistant chose `main.py` as the production composition root: it constructs one registry, ban and verified IP lists, request policy, and token reissuer, then supplies explicit dependencies to `BrowserApi` and `CompatibilityApi`. `Application` binds those instances to generated routers and captures error-display configuration per application. The diagnostic-IP setting is an injected callable and the MOTD directory is injected. Component imports no longer construct the production graph; importing `main:app` still does.

Previously `routes/shared.py` created process-global services on import. The new graph shares the same registry and policy within an application while allowing separate applications and tests to use independent services and IP-list files. The working-tree implementation and `test_dependency_injection.py` establish these mechanics; the precise historical motivation beyond the requested injection and isolation is not available. Registry state and signing keys remain process-local. Explicit constructors increase wiring at the composition boundary. Existing synchronous business handlers and HTTP behavior were to remain unchanged; this extends rather than supersedes [Contract packaging and synchronous handlers](2026-11-12-contract-packaging-and-sync-handlers.md).

The implementation replaces module-global service lookup rather than using globals, `app.state`, or request-time dependency resolution, as described in the uncommitted `CONTRIBUTING.md`. The available checkpoint does not establish whether those alternatives were separately considered or rejected, or their rationale. The existing expiry-preserving update lookup documented in [PR 13 compatibility corrections](2026-11-12-pr13-compatibility-corrections.md) remains present in the working tree.

## Validation and follow-up

This review ran the dedicated injection tests: six passed, with one Starlette deprecation warning. They cover shared instances, isolated registrations, lists and keys, injected token services, per-application error configuration, MOTD paths, and import side effects. The checkpoint reports 262 passing tests, successful CI, and bounded compatibility replay with 59 exact matches and three documented differences; these broader results were not independently rerun or verified here and do not prove complete HTTP equivalence.

Commit or otherwise preserve the implementation and rerun the relevant checks before relying on this uncommitted state. Reconsider the composition if deployment requires cross-process shared state or different service lifetimes, or if compatibility tests reveal changed behavior. The full conversation, exact rationale, and any other considered alternatives remain unknown.

## Subsequent developments (2026-11-13)

The implementation was committed and the follow-up interface wiring was added. The historical uncommitted status and commit follow-up above are outdated; the decision itself remains in effect. See [Dependency injection implementation and interface wiring](2026-11-13-injection-implementation-and-interface-wiring.md).
