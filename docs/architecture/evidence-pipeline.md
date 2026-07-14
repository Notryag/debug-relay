# Event and Evidence Pipeline

[Wiki Home](../README.md)

## Goal

Continuously turn noisy runtime failures into compact error groups, useful statistics, and a small
attributable evidence set that a development agent can inspect without receiving an entire log store
or production runtime.

## Event Processing Stages

1. Authenticate the source and map it to one project.
2. Validate event ID, schema, timestamps, content size, and repository identity.
3. Redact credentials, cookies, authorization headers, connection strings, private keys, and
   configured sensitive fields.
4. Normalize unstable values such as timestamps, UUIDs, generated IDs, ports, addresses, and
   temporary paths.
5. Compute a deterministic fingerprint from project scope, error type, normalized message, and
   stable stack frames.
6. Reject replayed project-scoped event IDs without changing aggregate counts.
7. Update the error group and one-minute occurrence bucket.
8. Evaluate deterministic detection rules.
9. When actionable, create a development case with a sanitized anchor-evidence sample and exact
   source revision.
10. Preserve bounded source references for later evidence enrichment.

AI is not used in these stages. A model receives selected case context only after deterministic
security, grouping, and detection decisions.

## Event Contract

Every event provides:

- project-scoped event ID
- UTC observation timestamp
- environment and component
- severity
- error type and message
- source adapter and locator
- optional bounded stack and attributes
- optional trace, request, job, or task correlation
- optional service and deployment identity
- registered repository ID and immutable commit when automatic case creation is expected

An adapter may provide a trusted source fingerprint, but DebugRelay still validates and scopes it.
The default server fingerprint remains deterministic and vendor-independent.

## Error Groups and Statistics

A group retains:

- normalized fingerprint
- project, environment, component, and error type
- normalized message
- total accepted count
- first and most recent occurrence
- highest observed severity
- latest release and repository identity
- bounded sanitized representative event
- one-minute count buckets
- active case ID when detection opened one

The system does not append every raw event body to the database. A compact receipt stores event ID,
group, observation time, receipt time, and sanitized content hash for idempotency and audit.

## Detection Order

Initial detection prefers:

1. first-seen `critical` and `error` groups with an immutable revision
2. severity escalation
3. significant count or rate increase over a project baseline
4. recurrence after a verified resolution
5. appearance on a release newer than the last verified fix
6. repeated warning groups crossing a configured threshold

Only the first rule is required for the first monitoring implementation. Each later rule needs
replayable event fixtures and false-positive measurements before becoming a default.

## Case Context Layers

### Summary

Contains error-group identity, counts, first and last seen, affected revision, top stable stack
frames, correlation identifiers, and the detector decision.

### Selected Evidence

Contains the sanitized representative error plus bounded correlated logs, requests, changes,
runtime observations, and attachment descriptors. Each item has an evidence ID and provenance.

### Source References

Contains authorized, queryable locations for follow-up evidence. An agent requests a narrow query;
DebugRelay enforces project, source, time, count, and byte limits.

## Fingerprint Normalization

A first-pass fingerprint combines:

```text
project + environment + component + error type
  + normalized message + top stable stack frames
```

Normalization removes values that split one error into many groups, such as timestamps, UUIDs,
hexadecimal addresses, numeric identifiers, ephemeral ports, and source line numbers. Secret
redaction happens first so secret values never influence or enter a fingerprint.

Fingerprints support grouping and retrieval; they never merge confirmed case histories without a
reviewed operation.

## Retention

- raw telemetry remains in its source system
- event receipts have short replay-protection retention
- occurrence buckets are compact and may be rolled up over time
- representative samples follow the project's sanitized-event retention policy
- selected case evidence follows case retention
- confirmed root cause, fix, and verification records have the longest retention

Related: [System Architecture](overview.md),
[Project Integration](../integrations/project-integration.md), and [Security](../security.md).
