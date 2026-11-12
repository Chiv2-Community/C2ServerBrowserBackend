# FastAPI alternative to generated Flask boundary

- Date: 2026-11-12
- Status: superseded
- Scope: backend web framework and generated API boundary
- Repository: C2ServerBrowserBackend, `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `refactor/oas-generated-api`; HEAD: `caecade2f491c7fddde3ba9067a44fd274b18227`; no exact tag; nearest release tag: `v1.1.2`.
- Source: user and build agent, session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d0998f63001dwK0qWdU4iILeV`. Earlier history was compacted.
- Follow-up source: same session, response `msg_1d09a30e9001FJiCmyMFNCoity`; recording HEAD `39e387e863857dbd2b1d522a8c6f26147c0b851a`, no exact tag, nearest release `v1.1.2`. Migration remains uncommitted.
- Related: [OpenAPI-first generated backend boundary](2026-11-12-openapi-generated-boundary.md), [backend issue #10](https://github.com/Chiv2-Community/C2ServerBrowserBackend/issues/10).

## Proposal and context

The user asked whether FastAPI could replace Flask. The agent recommended switching before the migration lands, while retaining OAS as the authority and generating Pydantic models, interfaces and FastAPI routers into the separate API package. Application code would implement the interfaces. OpenAPI Generator has a `python-fastapi` target; the agent therefore considered Smithy unnecessary for this proposal. Generator suitability for this specific contract was not demonstrated.

The [earlier boundary](2026-11-12-openapi-generated-boundary.md) selected `python-flask` to retain the existing HTTP stack. FastAPI is a subsequent alternative, not an approved reversal: the user asked a question and the agent made a recommendation, but the available conversation contains no approval or implementation of the switch. Current uncommitted templates and package still use Flask; HEAD records annals only, not the migration implementation.

## Consequences and validation

Switching would require ASGI startup and replacements for Flask-specific proxy handling, rate limiting and error handlers. Preserve existing URLs, JSON casing, defaults and error behavior; FastAPI's default 422 validation responses must not silently change the contract. The existing Flask migration already intentionally changes some malformed compatibility requests to 400, so exact legacy compatibility remains unresolved.

The earlier 198-test CI result and wheel/Docker checks apply to the Flask working tree, not FastAPI. They do not establish perfect equivalence. Before a drop-in claim, compare identical request sequences and state against baseline `80e1fae0e635d6ae1619ab75ea87a9add50749ef`, controlling time, UUIDs and signing keys; document intentional differences and validate real integrations. Reconsider the framework choice after generator, compatibility, deployment and maintenance evidence is available. No FastAPI benchmark, prototype, user approval or comparative assessment is available in the source.

## Generator follow-up (2026-11-12)

The user asked to avoid generated stubs that must be filled in. The agent inspected the pinned 7.17.0 [base API](https://github.com/OpenAPITools/openapi-generator/blob/v7.17.0/modules/openapi-generator/src/main/resources/python-fastapi/base_api.mustache) and [router](https://github.com/OpenAPITools/openapi-generator/blob/v7.17.0/modules/openapi-generator/src/main/resources/python-fastapi/api.mustache) templates: the generated base has typed async methods containing `...`, and the router discovers subclasses and instantiates the first, returning 500 if none is registered. Handwritten subclasses can be separate from generated files, but the default base does not enforce abstract methods or explicit implementation injection.

The agent proposed template overrides for those stronger interface properties, not an approved or tested implementation. The source templates support the described dispatch behavior; their suitability for this project's complete contract remains unverified. No framework switch was authorized by this follow-up.

## Subsequent developments (2026-11-12)

The proposal's historical statements that approval and implementation were unavailable are superseded by later user approval and an uncommitted FastAPI implementation. See [approved FastAPI boundary](2026-11-12-fastapi-generated-boundary.md) for provenance, evidence and remaining compatibility limits.
