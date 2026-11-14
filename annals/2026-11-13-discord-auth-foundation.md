# Discord authentication foundation and EOS retirement

- Date: 2026-11-13
- Status: implemented foundation; integration and activation pending
- Scope: backend signing, sessions, EOS authentication, cross-project admission
- Repository: C2ServerBrowserBackend, `git@github.com:Chiv2-Community/C2ServerBrowserBackend.git`
- Recording branch: `feature/discord-auth`; HEAD and implementation: `521001abf30788fbafb2c253ee96fba0669d2877`; no exact tag; nearest tag `v1.2.3` (`v1.2.3-1-g521001a`). The working tree was clean before this review.
- Source: user and build assistant, session `ses_e2fd4d988ffeEfPUe73w30m5Fd`, through response `msg_1d81ebe22001lmNdpzZmp6mZUH`; supplied checkpoint is compacted, not a complete transcript. Related: [backend #11](https://github.com/Chiv2-Community/C2ServerBrowserBackend/issues/11), [backend #12](https://github.com/Chiv2-Community/C2ServerBrowserBackend/issues/12), [plugin feasibility #34](https://github.com/Chiv2-Community/UnchainedPlugin/issues/34), and [implementation documentation](../docs/discord-auth.md).

## Decision and context

The checkpoint attributes to the user authorization to start Discord authentication from latest main and drop EGS/EOS authentication. This supersedes the EOS-preservation requirement attributed to backend #11, not Epic storefront support. The exact original wording and rationale for dropping EOS are unavailable; issue #11's contents were not independently verified. The committed contract and route retire the EOS exchange: a valid legacy login request receives HTTP 410 `auth_retired`, while malformed requests still undergo validation. EOS SDK models are removed. This is a compatibility break, not proof that existing joins work without the exchange.

The earlier [Discord admission plan](https://github.com/Chiv2-Community/C2ServerBrowserBackend/blob/caecade2f491c7fddde3ba9067a44fd274b18227/annals/2026-11-12-discord-admission-plan.md) was proposed, not deployed. Its centralized identity, host-controlled policy, disabled/required modes, bounded sessions and persistent keys remain the integration direction. The foundation implements part of that plan; the earlier record is absent from this branch, so no backlink can be safely added to it here.

## Choice and evidence

The committed [foundation documentation](../docs/discord-auth.md), contract, source and tests establish persistent RSA signing keys, overlapping public-key rotation, JWKS, an internal join-ticket signer, and a bounded transactional SQLite session store. Unconfigured signing publishes an empty JWKS; configured invalid key material fails startup rather than silently generating ephemeral keys. Tickets use a fixed HTTPS issuer, a live registration UUID audience and a 60-second lifetime. Rotation retains the prior public key for 90 seconds. Operators must provision and protect key material; persistent keys do not make the process-local registry multi-worker-safe.

Sessions store hashes of opaque rotating credentials, bound storage and expiry, and revoke the entire family on reuse of a retained spent credential. A lost successful rotation response requires reauthentication; retrying the old credential revokes descendants. This deliberately does not provide a response-recovery grace window or store replacement secrets. The documented security and bounded-storage constraints explain these mechanics; the historical comparison or rationale for selecting this retry tradeoff over other designs is unavailable. Storage quotas and lock failures have distinct behavior, and public HTTP mappings remain undefined.

OAuth, client handoff, public session and ticket operations, plugin validation/admission, and launcher policy are not implemented. Required authentication must remain disabled until integration and transport-security gates are met. A signed one-use bearer ticket can still be intercepted and raced; transport confidentiality and possible connection binding or proof of possession remain blocking design questions. Native Windows and Steam/Epic/Proton round trips are untested for this feature. Disabled mode preserves legacy joins without claiming verified identity; required mode must fail closed when eventually implemented.

## Consequences and follow-up

Regenerate consumers of removed EOS models, verify legacy join compatibility, and coordinate OAuth state/PKCE, bounded HTTP work and rate limits, client retry recovery, plugin admission, and launcher rollout before activation. Validate transport confidentiality and connection binding before exposing ticket issuance. Protect keyring and session database backups; restoring a session backup can resurrect revoked credentials. Reconsider the retry policy if client recovery requirements or a safe bounded response-recovery protocol change; reconsider ticket transport if feasibility evidence shows bearer credentials cannot be protected.

The checkpoint reports 393 tests, full local CI and compatibility replay with 57 exact cases and five documented differences. The implementation and test files exist, but those runs and results were not independently reproduced in this review. The commit is local on this branch; push, release and deployment are not established. No additional rejected alternatives, exact approval history, or complete prior conversation are available.

## Subsequent developments (2026-11-13)

The unconditional follow-up to regenerate EOS model consumers is superseded by the user's later report that nothing integrated with EOS authentication and request to remove consumer migration guidance. The technical compatibility break and integration gates are not refuted or waived. See [EOS consumer migration guidance](2026-11-13-eos-consumer-migration-guidance.md).

The intended session expiry, bounded cleanup and key overlap were retained, but review found timing and cleanup failures in their initial implementation. Later fixes coordinate signing cutover and adjust session transactions. The general 90-second overlap policy above is not proof that the initial implementation enforced it under delayed publication. See [authentication timing and cleanup corrections](2026-11-13-auth-timing-and-cleanup.md).
