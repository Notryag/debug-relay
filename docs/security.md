# Security

[Wiki Home](README.md)

## Security Goal

DebugRelay handles error data, repository identity, source locations, runtime metadata, and agent
output. Its default posture is bounded, read-only evidence collection with sanitized storage and
explicit human confirmation of resolution.

## Intake and Authentication

- Intake tokens are scoped to one project and stored as hashes.
- Human sessions, adapter credentials, and agent credentials use distinct scopes.
- Agent credentials may read assigned issues and report analysis but cannot confirm resolution.
- Requests enforce content type, item count, byte size, and rate limits before processing.
- Webhooks support replay protection and idempotent event IDs.

## Redaction

Redaction occurs before persistent storage and again before export as defense in depth. Policies
must cover:

- passwords and common secret-key fields
- API tokens and access keys
- cookies and authorization headers
- connection strings and private keys
- configured personal or tenant identifiers
- request and response bodies, which are excluded by default

Every evidence record stores the redaction-policy version and outcome. Redaction tests include both
known-secret fixtures and benign values that must remain intact.

The MVP stores and exports sanitized evidence only. Restricted raw-evidence retention is deferred.

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

- evidence intake and follow-up queries
- artifact download
- bundle export
- agent analysis writes
- resolution confirmation and reopening
- project adapter and policy changes

## Retention

Large and raw-like artifacts have the shortest retention. Sanitized selected evidence follows the
project policy. Confirmed root cause, fix, verification, and small evidence summaries may be retained
longer because they form the reusable case library.

Related: [Evidence Pipeline](architecture/evidence-pipeline.md),
[Project Integration](integrations/project-integration.md), and
[Development Agent Interface](integrations/agent-interface.md).
