# Product Vision

[Wiki Home](../README.md)

## Purpose

DebugRelay continuously observes software error signals, groups and measures repeated failures,
turns actionable groups into development cases, hands selected context to an AI development agent,
and records the human-verified fix.

Its purpose is:

> Detect code problems early, locate them quickly, and make every verified fix useful to the next
> occurrence.

The primary workflow begins with runtime events, not a developer filling in an issue form. Manual
issue creation remains a fallback for local reproduction and sources that cannot emit events.

DebugRelay is AI-native and model-agnostic. AI diagnosis is part of the case workflow, but models do
not inspect the unfiltered event stream and are not responsible for security filtering, grouping,
counting, or trigger decisions.

## Questions the Product Answers

For each project, a developer should be able to answer:

1. Which errors are new, increasing, recurring, or associated with a release?
2. How often did an error occur, where, and across which revisions?
3. Which bounded evidence caused DebugRelay to open a development case?
4. What did the development agent conclude, and which evidence or code supports it?
5. What change fixed the problem, how was it verified, and did the error stop recurring?

## Primary Workflow

```text
Applications / CI / Docker / Kubernetes / OpenTelemetry / error services
                                  |
                                  v
                   Authenticated error events
                                  |
                                  v
               Validate -> redact -> normalize -> fingerprint
                                  |
                                  v
                    Group -> count -> time buckets
                                  |
                                  v
            Detect new error / spike / regression / recurrence
                                  |
                                  v
            Automatically create or update a development case
                                  |
                                  v
                  AI agent diagnosis and code locations
                                  |
                                  v
                 Developer-confirmed fix and verification
                                  |
                                  v
                    Reusable case and detection feedback
```

## DebugRelay Responsibilities

- continuous authenticated intake from collectors, SDKs, webhooks, and observability adapters
- pre-storage redaction, normalization, deterministic fingerprinting, and idempotent receipts
- error groups with first seen, last seen, count, affected revision, and bounded time buckets
- deterministic detection of first-seen errors, volume changes, recurrences, and release regressions
- automatic development-case creation and evidence selection
- exact repository and release identity before agent handoff
- portable Issue Bundle generation for an external development agent
- structured agent analyses with evidence and source citations
- human-confirmed root causes, fixes, and verification results
- retrieval of similar resolved cases and feedback into later detection

## Data Boundary

DebugRelay is an error surveillance and development-case system, not a general log or metrics
database. Existing systems such as OpenTelemetry collectors, Sentry, Loki, Prometheus, CI services,
Docker, and Kubernetes remain sources of truth for broad telemetry.

DebugRelay stores:

- event IDs and hashes needed for idempotency
- normalized error-group identity and aggregate counts
- bounded time buckets and a small sanitized representative sample
- selected evidence attached to an actionable case
- agent analysis and verified resolution history

It does not retain an unbounded copy of every raw log line, trace, request body, or metric series.

## Development Agent Responsibilities

- read an automatically prepared case bundle and an authorized source checkout
- inspect the exact source revision associated with the detected error
- separate observed facts from hypotheses
- cite evidence IDs and concrete source locations
- propose bounded checks and code changes
- report diagnosis and verification results through the stable case interface

An agent may propose a fix, but only a developer can confirm that a case is resolved.

## Non-Goals

The first version is not:

- a general-purpose observability store or dashboard
- a pager, escalation-policy, or on-call scheduling product
- a replacement for GitHub Issues, Jira, Sentry, Prometheus, Grafana, or Loki
- a provider-specific model runtime or embedded chat product
- an autonomous production-remediation system
- a Kubernetes management platform

## Data Flywheel

Raw event volume is not the flywheel. The valuable reviewed chain is:

```text
Normalized error group and occurrence pattern
  -> detection decision
  -> selected evidence and exact revision
  -> agent hypotheses and checks
  -> confirmed root cause
  -> changed files and fix commit
  -> verification result
  -> post-fix recurrence or non-recurrence
```

Resolved cases improve later grouping, prioritization, evidence selection, and diagnosis evaluation.
Model training or fine-tuning remains deferred until representative human-reviewed cases exist.

Useful quality measures include:

- duplicate event rejection rate
- false error-group merge and split rates
- detection-to-case precision
- time from first occurrence to actionable case
- top-three root-cause accuracy
- whether a matched historical case shortened resolution time
- whether the error recurred after a confirmed fix

## First Reference Project

Dayboard may exercise the first end-to-end monitoring flow because its repository and Docker runtime
are locally available. The implementation must use generic structured-event, Git, Docker, file, and
HTTP contracts; no core field or service may contain a Dayboard-specific concept.

Related: [Core Workflow](workflow.md), [System Architecture](../architecture/overview.md), and
[MVP Plan](../mvp.md).
