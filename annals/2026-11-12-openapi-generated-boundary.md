# OpenAPI-first generated backend boundary

- Date: 2026-11-12
- Status: accepted
- Scope: backend API contracts, generated code, packaging and compatibility validation
- Repository: C2ServerBrowserBackend, `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `refactor/oas-generated-api`; HEAD: `80e1fae0e635d6ae1619ab75ea87a9add50749ef`; exact and nearest tag: `v1.1.2`.
- Implementation: uncommitted working-tree changes at recording time, including OAS, templates, generated package, application, tests, CI and Docker. No implementation commit is identified.
- Source: user and build agent in session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d09929e400103OtJNCqBB9lxe`; earlier conversation is compacted. Related: [backend issue #10](https://github.com/Chiv2-Community/C2ServerBrowserBackend/issues/10), [Discord plan](2026-11-12-discord-admission-plan.md).

## Decision and context

The user required the whole backend system to be OAS- or other IDL-first: generated models and APIs must not be edited by hand; application code implements API interfaces; generated sources belong in a separate package in a multi-package build. This is a prerequisite for planned Discord authentication. The user allowed Smithy/Smithplates if needed, without requiring a switch.

The build agent chose OpenAPI Generator `python-flask`, pinned at 7.17.0, with custom templates and a uv workspace package `server-browser-api`. This retains Flask while generating contract models, abstract interfaces and route bindings; handwritten handlers and domain conversions remain in the application. OAS, templates and generator configuration are the inputs, and CI regenerates to detect drift. This rationale is attributed to the agent's stated intent and the working-tree configuration; no comparative Smithy evaluation or rejection is evidenced. FastAPI templates were inspected, but no formal comparative evaluation is available.

## Evidence and consequences

Working-tree `codegen/config.yaml`, `pyproject.toml`, `scripts/generate_api.py`, generated package, and `ci.sh` support the selected architecture. The package and application are not yet committed. The implementation includes TBIO and PlayFab compatibility routes, contract validation, local-only schema references and response/route tests. Contributor instructions prohibit manual generated-source edits. The source conversation reports the old baseline passed 171 tests, and the later full CI run passed 198 tests, type checking, drift checks, both package builds and isolated wheel startup. It also reports a Docker build; this review did not rerun tests or Docker. The original tests were mechanically adapted, so their passage is not a byte-for-byte comparison with the baseline.

The agent explicitly corrected its earlier broad compatibility assertion: **perfect replacement has not been established**. Tests compare routes to the modified spec and exercise selected flows; the spec changed with the implementation. They do not prove identical bodies, headers, persisted state, error precedence or real plugin/launcher interoperability. Some malformed compatibility requests intentionally change from incidental 500 responses to JSON 400 errors. The exact extent of other differences remains unknown.

## Follow-up and reconsideration

Before claiming drop-in equivalence, run differential request sequences against baseline `80e1fae0e635d6ae1619ab75ea87a9add50749ef` and the candidate with controlled time, UUIDs and signing keys; compare status, headers, bodies and persistent state, including failure ordering, and document intentional differences. Validate real plugin and launcher integration. Reconsider generator or templates if contract fidelity, maintainability or interoperability cannot be demonstrated. The source's later compatibility qualification supersedes its earlier broad success assertion; it does not prove every original behavior differs.

## Subsequent developments (2026-11-12)

The agent later proposed FastAPI instead of the Flask selection described above. This is an unapproved alternative, not a superseding decision; see [FastAPI alternative](2026-11-12-fastapi-migration-proposal.md).

Later on 2026-11-12, the user approved FastAPI and the working tree was migrated. The Flask generator and retained-Flask stack choice, and the preceding statement that the alternative remained unapproved, are superseded; the broader OAS-first decision remains accepted. See [approved FastAPI boundary](2026-11-12-fastapi-generated-boundary.md).
