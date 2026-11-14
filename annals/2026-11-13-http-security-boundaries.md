# HTTP security boundaries and proxy trust

- Date: 2026-11-13
- Status: implemented locally after source response
- Scope: administrator credentials, forwarded headers, JSON request bodies
- Repository: C2ServerBrowserBackend, `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Branch: `feature/discord-auth`; recording HEAD: `edcc93f337c0f6a87ca6e17eeef79a2fe39635d4`; no exact tag; nearest release tag `v1.2.3` at `7b66edc60021cdbee8ffde64038b21c08f5a1d99`.
- Source: user and build assistant, session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d84b417a001mMFlXLJMugjY1q`. Earlier conversation is compacted and incomplete. Implementation and tests were uncommitted at the source response and when this review began.

## Decision and evidence

Following the user's request to find and patch vulnerabilities, the assistant chose three local changes:

- Reject empty or non-ASCII configured secret keys and reject non-ASCII supplied keys without a comparison exception. The prior implementation compared an empty configured key with the empty fallback for a missing admin header. The transcript reports a reproduction against the prior HEAD.
- Trust forwarded IP and scheme only when the immediate peer belongs to `TRUSTED_PROXY_CIDRS`, defaulting to IPv4 and IPv6 loopback; an empty list disables trust. Use the last forwarded IP only if valid, and accept only HTTP or HTTPS schemes. Previously any direct peer could supply forwarded headers. This changes the proxy assumption described in [unified request logging](2026-11-13-unified-request-log-format.md), while preserving request attribution and log formatting.
- Declare a 1 MiB JSON body limit in the OpenAPI contract and enforce it while streaming, returning HTTP 413 on excess. A content-length check alone would not bound an underdeclared or chunked stream; the added tests cover these cases. The cap does not bound slow connections or aggregate concurrent memory.

The assistant reported reproducing empty-key acceptance, arbitrary-peer forwarding and acceptance of an oversized body against the old implementation. The working-tree changes and regression tests are present; this review did not independently rerun the reproductions. The security rationale is attributed to the assistant's findings, not to an independently documented threat assessment. No other alternatives are evidenced.

## Consequences and validation

Non-loopback reverse proxies need their backend-facing network configured, and trusted proxies must overwrite forwarded headers. An overly broad allowlist restores spoofing risk. Existing empty or non-ASCII configured keys will fail instead of starting; deployments must choose an appropriate ASCII key. The body cap is a public compatibility constraint; proxy timeouts and concurrency limits remain necessary. OpenAPI and the generator template are the sources for the generated runtime.

The local CI log reports 423 passing tests, mypy across 105 files, current generated API and installed-wheel smoke checks; the transcript reports a successful compatibility replay. These runs were not repeated for this record. During this review another process committed the implementation as `1d3a1b9be658f0d120359941d9b76a6d307cdc0f`; no release, deployment or comprehensive security audit is established. Reconsider the proxy defaults for actual deployment topology, the body limit if legitimate payloads exceed it, and the key restriction if a secure compatible credential representation is required. Earlier deliberation and production traffic measurements are unavailable.
