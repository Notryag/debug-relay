# Core Workflow and Domain Model

[Wiki Home](../README.md)

## Workflow

```text
Runtime or delivery source
          |
          v
     ErrorEvent
          |
          v
 validate, redact, normalize, fingerprint
          |
          v
      ErrorGroup ----> OccurrenceBucket statistics
          |
          v
     detection policy
          |
          v
 DevelopmentCase (portable Issue Bundle)
          |
          v
   AgentAnalysis
          |
          v
 human-confirmed Resolution
          |
          v
 recurrence feedback into the ErrorGroup
```

Continuous event intake is the primary entry point. A manual case is a fallback for local failures,
developer observations, and integrations that cannot yet emit structured events.

## Core Concepts

### Project

Project identity, registered repositories, scoped intake and agent credentials, event sources,
detection policy, redaction policy, and retention limits.

### ErrorEvent

One source observation of a failure. It has a project-scoped idempotency ID, UTC timestamp,
environment, component, severity, error type and message, optional stack, provenance, correlation
IDs, and release or repository identity.

An event is untrusted input. DebugRelay validates and sanitizes it before computing a fingerprint or
persisting any sample. A compact receipt may be retained for replay protection; the entire raw event
stream is not the long-term product record.

### ErrorGroup

A deterministic aggregation of equivalent events within a project, environment, and component. It
records a normalized fingerprint, first and last occurrence, total count, highest severity, latest
known release, a bounded sanitized sample, and its active development case if one exists.

Grouping does not merge development history. A recurrence or regression may create a new case while
remaining associated with the same long-lived error group.

### OccurrenceBucket

A bounded time bucket containing the number of accepted events for one error group. Buckets support
trend and spike detection without retaining every raw event. The MVP uses one-minute UTC buckets.

### DetectionPolicy

Deterministic rules decide when a group becomes actionable. Useful triggers include:

- a first-seen `error` or `critical` event with an immutable source revision
- a count or rate threshold within a time window
- recurrence after a confirmed resolution
- a fingerprint appearing on a new release
- severity escalation

The first monitoring slice implements the first-seen trigger. Rate, regression, and recurrence
detectors follow after enough event data exists to test them.

### DevelopmentCase

The actionable debugging record created by a detector. The existing REST and Issue Bundle v1
contract currently call this record an `Issue`; product documentation uses `DevelopmentCase` to
distinguish it from raw events and error groups.

A case contains the symptom, selected evidence, exact source revision, state, agent analyses, and
eventually a human-confirmed resolution. A detector may create a case automatically; manual creation
uses the same downstream contract.

### Evidence

A sanitized, bounded observation selected for one case. Evidence preserves its source, observation
time, collection time, content hash, redaction status, and relationship to the anchor event.

### AgentAnalysis

An agent's observed facts, ranked hypotheses, cited evidence, source-code locations, missing
information, proposed changes, and verification steps.

### Resolution

The developer-confirmed root cause, changed files, fix revision, verification procedure and result,
and affected conditions.

## Lifecycles

Error groups are durable aggregate identities. They may exist without an actionable case when a
revision is missing or a detection threshold has not been met.

Development cases retain the small lifecycle:

- `open`: automatically detected or manually recorded and awaiting analysis
- `analyzing`: an agent or developer has submitted active analysis
- `resolved`: a developer confirmed root cause, fix, and verification

Agent output alone cannot resolve a case. A later recurrence preserves the prior resolution and
opens a new case rather than silently overwriting history.

## Invariants

- Event IDs are idempotent within a project.
- Redaction precedes fingerprinting, sample storage, and case evidence creation.
- Group counts increase only for accepted, non-duplicate events.
- Every event retains source provenance and an observation timestamp.
- Every automatically opened case identifies an immutable source revision.
- Error groups may be merged or split only through explicit reviewed operations, not model output.
- Agent facts cite evidence IDs or source-code locations.
- A resolution records both the fix and how it was verified.
- Only a human-authorized action confirms resolution.

Related: [Product Vision](vision.md), [Evidence Pipeline](../architecture/evidence-pipeline.md), and
[Development Agent Interface](../integrations/agent-interface.md).
