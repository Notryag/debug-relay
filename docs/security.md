# Security

[Wiki Home](README.md)

## Security Goal

DebugRelay continuously handles untrusted error events, repository identity, source locations,
runtime metadata, and agent output. Its default posture is authenticated bounded intake, redaction
before fingerprinting or storage, aggregate rather than raw-event retention, read-only collection,
and explicit human confirmation of resolution.

## Current Implementation Status

The local backend currently provides separate admin, project-intake, and project-agent bearer-token
scopes; hashed project tokens; cross-project isolation; pre-storage evidence redaction; bounded
evidence sizes; immutable source revisions; human-only resolution confirmation; project-scoped event
idempotency; aggregate-only monitoring storage; and redaction before fingerprinting.

It is not ready for public internet exposure. Human session authentication, request-rate limiting,
signed webhook verification, audit-event retention, token rotation, receipt expiration, and external
artifact storage remain implementation requirements.

## Intake and Authentication

- Intake tokens are scoped to one project and stored as hashes.
- Intake credentials are write-only for monitoring resources; group list and detail require agent or
  admin scope.
- Event IDs are unique within a project and retries preserve the original ID.
- Human sessions, adapter credentials, and agent credentials use distinct scopes.
- Agent credentials may read assigned issues and report analysis but cannot confirm resolution.
- Requests must enforce content type, item count, byte size, and rate limits before processing.
- Webhooks must support signature verification, replay protection, and idempotent event IDs.

Continuous sources also require per-project event-rate, body-size, attribute-count, stack-size, and
clock-skew limits. A successful duplicate response must reveal no data outside the token's project.

## Redaction

Redaction occurs before fingerprinting, grouping samples, persistent evidence storage, and export.
Policies must cover:

- passwords and common secret-key fields
- API tokens and access keys
- cookies and authorization headers
- connection strings and private keys
- configured personal or tenant identifiers
- request and response bodies, which are excluded by default

Every group sample and evidence record stores the redaction-policy version and outcome. Fingerprints
must be computed only from sanitized normalized values so secrets cannot become stable identifiers.
Redaction tests include known-secret fixtures and benign values that must remain intact.

The MVP stores compact receipts, aggregates, bounded sanitized samples, and selected case evidence.
Restricted raw-evidence retention is deferred.

## Repository Access

- Projects explicitly register repository locators.
- Local repository access is restricted to allowlisted workspace roots.
- Remote source-provider credentials are scoped and never placed in issue bundles.
- Issues cannot introduce an arbitrary path or repository credential.
- Bundles identify exact revisions; mutable branch names are not sufficient for agent handoff.

## Runtime Access

Adapters are read-only by default. DebugRelay does not grant a development agent production shell,
database write, service restart, deployment, rollback, or deletion capability.

Kubernetes credentials exclude Secrets, pod execution, mutation, and deletion. Docker access must
account for the authority of the Docker socket; prefer a narrow collector boundary instead of
exposing that socket to the core API or development agent.

## Artifact Storage

- Artifact names are generated server-side rather than trusted as filesystem paths.
- Uploads have media-type, size, and count limits.
- Content hashes detect corruption and identify manifest entries.
- Downloads verify project and issue authorization.
- Expired content is removed according to project retention policy while metadata records the
  expiration.

## Audit and Provenance

Record actor, action, issue, project, source scope, and time for:

- event acceptance, duplicate rejection, and detection decisions
- automatic case creation and error-group changes
- evidence intake and follow-up queries
- artifact download
- bundle export
- agent analysis writes
- resolution confirmation and reopening
- project adapter and policy changes

## Retention

Event receipts have short replay-protection retention. Occurrence buckets may roll up over time;
bounded group samples and selected case evidence follow project policy. Large artifacts have the
shortest retention. Confirmed root cause, fix, verification, and small evidence summaries may be
retained longer because they form the reusable case library.

Related: [Evidence Pipeline](architecture/evidence-pipeline.md),
[Project Integration](integrations/project-integration.md), and
[Development Agent Interface](integrations/agent-interface.md).
