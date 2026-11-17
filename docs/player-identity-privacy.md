# Player identity privacy: deployment review

Reviewed 2026-11-16. This is an engineering checklist, **not a published privacy
notice or a legal compliance determination**. The service operator must resolve
the open items for its jurisdiction before public deployment.

## Why this matters

Stable PlayFab, Steam and EOS identifiers, their cross-account associations,
login dates and mismatch records can identify or single out players indirectly.
Treat them as personal data, even without names or email addresses. A UUID,
hash or pseudonym does not by itself make these records anonymous.

Open-source licensing, volunteer operation and a free service are not blanket
GDPR exemptions. EU/EEA establishment, offering services to people there, or
monitoring their behaviour can bring processing within scope. Mere worldwide
website accessibility does not by itself establish targeting. Assess the actual
operator, service offering and data flows. UK GDPR has its own territorial rules.

Publishing source code is distinct from operating a backend that processes user
data. Identify who decides the purposes and means of the central identity service
and of each host's records. They may have separate controller responsibilities;
do not assume every community host is simply the backend's processor.

## Current data flow and gaps

| Data | Processing and recipients | Current retention |
| --- | --- | --- |
| PlayFab ID, EOS PUID, optional Steam ID, account UUID, first/last issuance dates | Private SQLite `user_accounts`; backend operators; identity claims also go to the selected game host | No automatic expiry or erasure workflow |
| Attempted independently verified combinations, reason, dates, count | Private SQLite `validated_mismatches`; authorized backend support | Deduplicated, but no age-based retention or erasure workflow |
| EOS Connect token and challenge completion secret | Client to backend; verification in memory | Not intentionally persisted; inspect ingress/APM/debug logging separately |
| Public PlayFab proof commitment | Temporarily published by the client; read by the independent verifier | Client attempts cleanup and confirms it; interrupted clients can leave a commitment behind |
| Reusable player PlayFab session | Client to fixed PlayFab HTTPS endpoints only | Not forwarded to the backend/host or stored in these tables |
| Operator verifier session | Provisioned to the backend for independent provider reads | Provisioning/renewal remains operationally incomplete; protect as a secret |
| Signed admission JWT | Backend to client to selected host, including native travel options | At most 60 seconds; bearer token, not an encrypted container |
| Replicated native IDs | Host and connected clients through native PlayerState replication | Controlled by the game, peers and their logs, not just the backend database |
| IPs, request metadata, game/host logs, support tickets, backups and telemetry | Deployment-dependent; may include reverse proxy and Graylog providers | Must be inventoried and assigned separate retention rules |

Current safeguards include independent proofs, generic mismatch responses, private
database files, bounded storage, no public association lookup, and no intentional
raw-token logging in the new identity flow. They do not establish compliance.
The SQLite database is not encrypted by the application. A 0600 file mode does not
protect a stolen disk, a compromised operator account, or copies/backups.

## Decisions required before deployment

- Name the operator/controller and publish a working privacy/support contact.
- Document purpose and lawful basis separately for account pinning, mismatch
  auditing, support and ordinary request logs. Security/abuse prevention may
  support legitimate interests, but requires a necessity/balancing assessment;
  it is not an automatic exemption. A plugin opt-in flag is not GDPR consent.
- Publish an accurate notice before collection, accessible from the actual join
  workflow. Explain fields, sources, recipients (including hosts/peer replication),
  purposes, basis, retention/criteria, rights, complaints and relevant transfers.
  No notice integration or acceptance UI is implemented by this document.
- Set justified retention/review periods separately for active pins, inactive pins,
  rejected combinations, logs and backups. Row/page budgets are not retention
  periods. Retaining every failed combination forever needs its own justification.
- Provide an authenticated support process for access, correction, erasure,
  restriction and objections where applicable. GDPR requests generally need a
  response within one month; document permitted extensions/refusals. Do not demand
  government ID or reusable login credentials by default.
- Scope any export/search to identifiers the requester is authorized to access.
  A mismatch can involve different people: a full conflicting row or association
  graph must not automatically be disclosed to either claimant.
- Resolve how a lawful deletion/restriction interacts with account pinning.
  Deleting a pin reopens first-use registration; silently retaining an identifier
  hash or tombstone is still data processing, not automatic anonymisation. Do not
  implement automatic eviction as a privacy fix without reviewing the security
  and legal effects. Document any justified retained subset and review date.
- Keep mismatch records factual: independently valid proofs conflict with a pin.
  They do not prove maliciousness, cheating or that both accounts are one person.
  Provide human review for mistaken pins. Assess automated-decision rules if the
  denial has legal or similarly significant effects; not every game rejection
  necessarily meets that threshold.
- Restrict operator access; secure/encrypt disks and backups as appropriate;
  test restore/deletion procedures; disable production debug/body/URL logging that
  could capture proofs or travel JWTs. Database deletion alone does not erase
  backup, SQLite free-page, journal, host-log or support copies.
- Document hosting/telemetry processors, contracts and international transfer
  safeguards where needed. Have a breach triage/contact process; GDPR notification
  may be required within 72 hours of awareness, subject to its risk thresholds.
- Assess whether a processing register, DPIA, representative or DPO is required
  for the actual deployment; neither assume all are mandatory nor assume a small
  volunteer team is exempt from everything.

Do not publish real-player database snapshots, account graphs or raw proofs in
issues, logs, Git fixtures or runtime reports. Use synthetic IDs in public tests.

## Other rules to check

- UK GDPR and the Data Protection Act for relevant UK processing.
- Applicable US state privacy/security and breach-notification laws. CCPA is not
  universally applicable: its covered-business definitions and thresholds matter.
- Children's privacy rules if the service is directed to children or the operator
  has relevant knowledge; a game's age rating is not a complete assessment.
- Epic, Steam and PlayFab terms governing provider data, credentials and disclosure.

The operator's location, hosting/subprocessors, intended player regions, audience
and legal structure are still needed for a jurisdiction-specific assessment.
Get qualified legal advice on that assessment rather than describing this branch
as "GDPR compliant".

## Authoritative references

- [EDPB: personal data, scope and principles](https://www.edpb.europa.eu/sme/learn-the-basics/data-protection-basics_en).
- [EDPB: lawful bases](https://www.edpb.europa.eu/sme/be-compliant/process-personal-data-lawfully_en).
- [EDPB: individual rights and request handling](https://www.edpb.europa.eu/sme/be-compliant/respect-individuals-rights_en).
- [EDPB: breach handling](https://www.edpb.europa.eu/sme/assess-the-risks/data-breaches_en).
- [ICO: UK GDPR scope](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/personal-information-what-is-it/who-does-the-uk-gdpr-apply-to/).
- [California Attorney General: CCPA scope](https://oag.ca.gov/privacy/ccpa).
