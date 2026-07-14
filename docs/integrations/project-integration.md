# Project Integration

[Wiki Home](../README.md)

## Principle

A useful integration continuously emits bounded structured error events with stable project,
runtime, and release identity. It may reuse an existing OpenTelemetry collector, error service,
webhook, CI system, Docker source, or Kubernetes adapter; DebugRelay does not require a proprietary
runtime agent.

Every adapter maps source-specific data into the shared `ErrorEvent` contract. Adapters never define
new core workflow states or write database tables directly.

## Minimum Integration Standard

Every integrated project provides:

- stable project, environment, component, and service identity
- a unique event ID for retry-safe delivery
- UTC observation timestamps
- severity, error type, message, and optional bounded stack
- source adapter and locator provenance
- at least one registered repository
- immutable commit or image-to-commit mapping for automatic agent-ready cases
- scoped intake credentials
- per-source event and byte limits
- redaction, detection, and retention policy

Configuration is represented by key name, revision, or fingerprint. Secret values, arbitrary request
bodies, and full environment dumps must not be collected.

## Integration Levels

### Level 1: Structured Events

- push validated errors to the event API or generic webhook
- include event ID, project, environment, component, error, and timestamp
- retry with the same event ID after transient failure
- optionally include repository commit and correlation IDs

This is the minimum useful always-on integration.

### Level 2: Release-Aware

- attach immutable repository commit, image digest, deployment ID, and service version
- map frontend assets to matching source maps and source revision
- enable automatic case creation and release-regression detection

### Level 3: Correlated

- propagate trace, span, request, task, and job identifiers
- expose bounded read-only log, trace, runtime, and deployment queries
- let DebugRelay enrich a detected case without copying the full telemetry stream

### Level 4: Runtime-Aware

- provide read-only Docker or Kubernetes state, selected logs, events, rollout status, and image
  identity
- allow bounded follow-up evidence queries from an authorized development agent

Manual case creation is a fallback integration mode, not Level 0 of the primary monitoring path.

## Adapter Contract

An adapter must:

1. authenticate its source or caller
2. map source identity to exactly one configured project
3. generate or preserve a stable project-scoped event ID
4. enforce source-specific event-count and byte limits
5. emit a validated `ErrorEvent`
6. preserve source locator, selector or query, time, and release identity
7. retry at least once delivery without changing the event ID
8. checkpoint polling or stream cursors durably when applicable
9. report partial collection and permission failures explicitly
10. avoid runtime mutation

Adapters are replaceable without changing error-group or case meaning.

## Initial Adapters

Implementation order:

1. generic structured HTTP event intake
2. generic signed webhook envelope
3. Docker log and container-identity collector for local dogfooding
4. OpenTelemetry log or exception mapping
5. CI test-failure and deployment events
6. Kubernetes workload, event, and bounded-log collector

Sentry, GitHub, GitLab, Loki, and similar products can later translate webhooks or query results into
the same event and evidence contracts.

## Kubernetes Adapter

Kubernetes workloads should expose or annotate repository locator, commit SHA, service version,
image digest, deployment identity, and source-map revision where applicable.

The adapter may read bounded pods, logs, events, deployments, ReplicaSets, Jobs, and rollout state.
Its service account must not read Secrets, execute inside pods, mutate resources, or delete objects.

Kubernetes evidence can identify restarts, failed probes, scheduling failure, eviction, rollout
failure, and out-of-memory termination. Application error identity and exact source revision remain
necessary for code-level diagnosis.

## Manual Fallback

The existing REST and CLI case-creation endpoints remain useful for local reproduction, one-off test
failures, and adapter development. They are low-level interfaces and must not define the default
product experience.

Related: [Event and Evidence Pipeline](../architecture/evidence-pipeline.md),
[System Architecture](../architecture/overview.md), and [Security](../security.md).
