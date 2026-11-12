# Approved FastAPI generated boundary and typed IP models

- Date: 2026-11-12
- Status: implemented (originally accepted with implementation uncommitted; see subsequent developments)
- Scope: generated backend boundary, ASGI deployment, IP serialization and compatibility
- Repository: C2ServerBrowserBackend, `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `refactor/oas-generated-api`; recording HEAD: `b3ca7081349c1cd4dbdb7fdf7198592ace830044`; no exact tag; nearest release tag: `v1.1.2` at `80e1fae0e635d6ae1619ab75ea87a9add50749ef`.
- Source: user and build agent, session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d0b13158001FohrTMpOs1U15H`; the supplied checkpoint summarizes this source, and earlier conversation is compacted. The original full discussion is unavailable to this review.
- Implementation: extensive uncommitted and untracked working-tree changes; no implementation commit or release identified. Related: [backend issue #10](https://github.com/Chiv2-Community/C2ServerBrowserBackend/issues/10).

## Decision and context

The checkpoint attributes approval to the user to replace the uncommitted generated Flask boundary with OpenAPI Generator `python-fastapi` 7.17.0, keeping OAS as the contract and generated code separate from application implementations. Template overrides provide abstract interfaces and explicitly injected implementations rather than requiring edits to generated stubs. This advances the [FastAPI proposal](2026-11-12-fastapi-migration-proposal.md) and supersedes the Flask generator and HTTP stack choice in the [earlier boundary](2026-11-12-openapi-generated-boundary.md), not its broader OAS-first decision.

Run ASGI directly with Uvicorn; remove Gunicorn as optional. The checkpoint supplies that rationale but no further deployment comparison. The proposal had identified FastAPI's default validation behavior, proxy handling, rate limiting and error handling as migration risks. Flask was the earlier choice to retain the existing stack; the evidence does not establish a separate detailed rejection rationale or a benchmark comparison.

Generated IP fields use typed IPv4/IPv6 values. TBIO serializes IPv6 with brackets; diagnostics and PlayFab use raw literals. The checkpoint reports that `serialize_as_any=True` bypassed field serializers and caused a bracket regression before removal. The current IP-model tests cover typed values and format distinctions; this review did not independently reconstruct the regression's full history.

## Evidence and consequences

The working tree's `codegen/config.yaml`, `codegen/templates/`, `pyproject.toml`, `scripts/entrypoint.sh`, `CONTRIBUTING.md` and IP-model tests support the implementation described above. The entrypoint directly invokes Uvicorn. The source checkpoint reports 236 passing tests, clean mypy and generation checks, wheel and Docker smoke tests, and real IPv6 loopback validation. These are reported results, not checks rerun by this review.

The checkpoint reports differential replay against `80e1fae0e635d6ae1619ab75ea87a9add50749ef`: 59 matching HTTP/state cases and three documented differences. Missing admin headers for two list reads change accidental 500 responses to 403; explicit null local IP remains 400 but the error names `str` instead of `IPAddress`. `scripts/check_compatibility.py` and `CONTRIBUTING.md` document these allowances and bounded scope. Replay improves evidence but does not prove complete legacy equivalence or real plugin/launcher interoperability.

## Follow-up and reconsideration

Review and commit the implementation separately; regenerate and run CI, wheel and deployment checks on the final tree. Validate real integrations and expand differential coverage where failure ordering, state, headers or deployment behavior matter. Reconsider templates or framework if compatibility, operational behavior or maintainability prove inadequate. Full source discussion, exact approval wording, independent reproduction of reported results and any comparative framework benchmark remain unavailable.

## Subsequent developments (2026-11-12)

The statements that the implementation was uncommitted and still needed a commit are superseded: implementation commit `f8f671f9bb74d4251b0fe3128ae686c43a4df161` exists. See [FastAPI implementation commit](2026-11-12-fastapi-implementation-commit.md) for provenance and validation limits.
