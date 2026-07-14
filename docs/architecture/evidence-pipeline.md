# Evidence Pipeline

[Wiki Home](../README.md)

## Goal

Convert a noisy problem report and its surrounding data into a small, attributable evidence set
that a development agent can inspect without receiving an entire log store or production runtime.

An issue starts from an anchor event: a manual report, exception, failed job, test failure, webhook,
or another concrete symptom. Collection expands outward from that anchor under explicit scope and
size budgets.

## Processing Stages

1. Validate schema, source identity, size, encoding, and timestamp.
2. Redact credentials, cookies, authorization headers, connection strings, and configured sensitive
   fields before persistent storage.
3. Normalize unstable values such as timestamps, UUIDs, generated IDs, ports, and temporary paths.
4. Correlate by project, environment, service, version, trace ID, request ID, job ID, and time range.
5. Group repeated log templates and retain counts, first and last occurrence, and representative
   samples.
6. Prefer application stack frames, relevant source files, and recent changes over unrelated output.
7. Apply per-type item and byte budgets.
8. Preserve references to additional authorized evidence that an agent may request later.

Deterministic code performs these stages. A model is not the first security or relevance filter.

## Context Layers

### Summary

Contains the symptom, source revision, top application stack frames, correlation identifiers, and
recent relevant changes. It should be sufficient for an agent to choose its first investigation.

### Selected Evidence

Contains bounded logs, requests, runtime observations, change metadata, and attachment descriptors.
Each item has an evidence ID and provenance.

### Source References

Contains authorized, queryable locations for follow-up evidence. The agent requests a narrow query;
DebugRelay enforces project, source, time, result-count, and byte limits.

## Evidence Record

Every item records at least:

- evidence ID and kind
- project, environment, and component
- observed time or time range
- collection time
- source adapter and source locator
- query, selector, or correlation basis
- source revision when applicable
- content type, size, and content hash
- redaction policy version and result
- relationship to the anchor event

Evidence content is not silently edited after handoff. Corrections, summaries, and derived samples
are new evidence records linked to their inputs.

## Relevance Order

Collection generally prefers:

1. the exception, failure, or reported symptom itself
2. events with the same trace, request, task, or job identifier
3. nearby events from the same service and revision
4. dependency and runtime state in the same time window
5. deployments, commits, migrations, and configuration fingerprints near the failure
6. code at the top application stack frames and relevant recent diffs
7. similar confirmed historical cases

This order is a default, not a hard-coded assumption for every adapter.

## Deduplication and Fingerprints

A first-pass error fingerprint may combine:

```text
project + component + exception type + normalized message + top stable application frames
```

Revision, route, or operation identity may refine a fingerprint where needed. Fingerprints support
retrieval and grouping; they must not automatically merge case histories without review.

Repeated log templates retain:

- occurrence count
- first and last observed time
- a bounded set of representative samples
- any change in severity or associated correlation identifiers

## Metrics and Runtime Data

If metrics are attached, export anomalies, baseline comparisons, aggregate values, and source query
references rather than complete raw series. Runtime collectors should describe observed state and
identity, not grant the development agent direct production access.

## Retention

Sanitized, selected evidence may live with the issue according to project policy. Large or raw
artifacts have shorter retention by default. Confirmed resolution records and small evidence
summaries can be retained longer because they form the reusable case library.

Related: [Issue Bundle v1](../contracts/issue-bundle-v1.md),
[Project Integration](../integrations/project-integration.md), and [Security](../security.md).
