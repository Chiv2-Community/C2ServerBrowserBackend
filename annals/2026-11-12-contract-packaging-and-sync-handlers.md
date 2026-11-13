# Contract packaging and synchronous handlers

- Date: 2026-11-12
- Status: implemented
- Scope: generated API package and business-handler execution
- Repository: C2ServerBrowserBackend; remote: `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `refactor/oas-generated-api`; recording HEAD: `442a248c0ce8059b8f71c1fac537619ad05a4083`; no exact tag; nearest tag: `v1.1.2` (`80e1fae0e635d6ae1619ab75ea87a9add50749ef`).
- Source: user and assistant conversation `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d2f4b975001GBQQ7X96RBeoEE`, supplied as a partly compacted checkpoint. Earlier discussion and exact approval wording are unavailable.

## Decision and evidence

The checkpoint attributes two choices to the user: retain synchronous business handlers for now, and generate bundled OpenAPI YAML and JSON at package build time rather than track copies. Generated Python remains tracked. The actual reasons and any additional alternatives discussed are not recoverable from the checkpoint; do not infer a benchmark or performance rationale.

Commit `bcade3f9959d3889929ca95e6cf460562b171646` implements contract packaging: `packages/server-browser-api/hatch_build.py` reads the authoritative YAML, generates bundled resources for builds, and includes the source in sdists. Build-time PyYAML is required, but Java is not; `CONTRIBUTING.md` describes editable installs and the checks. The prior alternative, tracked bundled copies, was removed in that commit. The source and contract resources can diverge locally until regenerated; contract and wheel checks are intended to detect drift.

The generated router template dispatches synchronous implementation methods via Starlette's `run_in_threadpool`; this was already present in implementation commit `f8f671f9bb74d4251b0fe3128ae686c43a4df161`. `scripts/entrypoint.sh` runs Uvicorn with a configurable worker count. Retaining synchronous handlers defers an async conversion; its costs and any concrete conversion proposal are not established here.

## Validation, follow-up and history

The checkpoint reports 239 passing tests and bounded compatibility replay. Neither was rerun for this record; they do not establish complete compatibility. Reconsider packaging if artifact integrity or offline build requirements change, and handler execution if measured workload or blocking behavior warrants it. Exact rationale, alternatives, benchmarks and full earlier discussion remain open.

Earlier FastAPI annals at commit `fe989ff` recorded the generated boundary and direct Uvicorn deployment; these choices do not supersede that boundary. Those annals were removed by `029f5cd076cc2e3e7762a2842b7d1e577ee61970` and `/annals/` was ignored by `4a98ead6706b28a7bfdd0b4b0d8d0c8c6433d2e9`. The checkpoint reports this removal and ignore were requested by the user. The old records remain accessible in Git history, not as current files; no correction to their claims was established.

## Subsequent developments (2026-11-13)

A separate models/client/server package split was proposed for review; the combined API package and build-time contract packaging described above remain implemented, not superseded. See [Separate Python SDK packages proposed](2026-11-13-python-sdk-packaging-proposal.md).
