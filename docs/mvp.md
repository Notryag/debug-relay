# MVP Plan

[Wiki Home](README.md)

## Goal

Prove that a real application error can be observed automatically, deduplicated and grouped,
converted into an agent-ready development case with the correct source revision, analyzed by an
external AI development agent, and returned as a human-confirmed reusable resolution.

The agent runtime may remain external. The primary path must not require a developer to author an
issue form or JSON request.

## Current Progress

Downstream case workflow already complete:

- Issue Bundle v1 JSON Schema and portable examples
- PostgreSQL case, evidence, analysis, and resolution storage
- scoped project tokens, evidence redaction, REST case workflow, and ZIP export
- deterministic similar resolved-case retrieval
- REST-backed CLI for operational and agent handoff tasks

First monitoring slice complete:

- product and architecture centered on continuous event intake
- `ErrorEvent`, `ErrorGroup`, receipt, and occurrence-bucket persistence
- deterministic fingerprinting, idempotent ingestion, and first-actionable-event detection
- automatic agent-ready case creation when an error includes an immutable revision
- group list and detail APIs plus CLI inspection commands

## Monitoring Vertical Slice

1. Register a project and repository once.
2. Continuously submit structured runtime errors with stable event IDs.
3. Redact and normalize each event before fingerprinting or storage.
4. Reject duplicate deliveries without incrementing counts.
5. Group equivalent errors and update one-minute occurrence statistics.
6. Automatically open one case for a new error group with an immutable commit.
7. Export the generated Issue Bundle to an external development agent.
8. Accept structured analysis with evidence and source-code citations.
9. Let a developer confirm root cause, fix revision, checks, and outcome.
10. Observe whether the group recurs after the verified fix.

## Required Interfaces

- structured event intake API
- error-group list and detail API with occurrence buckets
- existing REST resources for cases, evidence, analyses, resolutions, and bundles
- CLI group inspection, case export, analysis report, and resolution commands
- error-group inbox, group detail, case detail, and project integration settings

MCP follows the stable REST and bundle contract. It is not required to prove the first file-based
agent handoff.

## Acceptance Criteria

- duplicate delivery of one event ID changes no count and creates no second case
- equivalent sanitized errors produce one group and correct aggregate counts
- a new `error` or `critical` group with a registered immutable revision opens one case
- an event without a source revision remains observable but is not handed to an agent
- no raw unbounded event stream is retained in DebugRelay
- configured secret fixtures never appear in a fingerprint, sample, evidence, or exported bundle
- the automatically generated case identifies the exact source revision
- one real AI development agent completes an analysis round trip
- facts and hypotheses reference evidence IDs or source locations
- only a developer can confirm resolution
- a resolution records root cause, fix revision, verification procedure, and result
- no core schema or service contains a Dayboard-specific field

## First Reference Case

Dayboard is the first dogfood source because its repository and Docker runtime are local. The
acceptance case uses only generic structured-event, Git, file, HTTP, and Docker contracts.

The case includes:

- one reproducible application error emitted without manual issue creation
- one exact repository revision
- at least two duplicate or equivalent deliveries proving grouping and idempotency
- a bounded stack or log sample
- an automatically generated case
- agent analysis citing evidence and a source location
- a real or fixture fix revision and focused verification command

## Deferred Scope

- high-volume raw log and metric retention
- automatic model-provider invocation and budgets
- built-in coding-agent orchestration
- pager and on-call escalation management
- autonomous code merge, deployment, rollback, or remediation
- multi-tenant SaaS administration
- Kubernetes Operator and node-level collector
- embedding search and fine-tuning
- replacement of existing observability or issue-tracking systems

## Delivery Stages

1. Complete: downstream case, evidence, agent, resolution, bundle, and similarity workflow.
2. Complete: operational CLI and file-oriented agent handoff.
3. Complete: event contract, receipts, grouping, time buckets, and first-actionable-event detector.
4. Next: add generic webhook and Docker collector with durable cursors and retries.
5. Build error-group inbox, group detail, case detail, and project integration settings.
6. Complete one real AI development-agent analysis and resolution round trip.
7. Add rate, recurrence, and release-regression detectors with replay fixtures.
8. Add OpenTelemetry and CI adapters.
9. Add MCP and Kubernetes adapters only after core monitoring contracts are stable.

## Remaining Decisions

- initial default thresholds after the first-seen detector
- receipt, bucket, sample, and case retention periods
- repository-locator to authorized-workspace mapping
- first external development agent used for acceptance testing
- exact Dayboard dogfood error

Related: [Product Vision](product/vision.md), [System Architecture](architecture/overview.md), and
[Event and Evidence Pipeline](architecture/evidence-pipeline.md).
