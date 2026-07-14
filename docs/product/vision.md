# Product Vision

[Wiki Home](../README.md)

## Purpose

DebugRelay is an AI-native, model-agnostic developer tool for capturing a software problem,
packaging the relevant context, handing that context to a development agent, and recording the
verified fix.

Its purpose is:

> Make every debugging session useful to the next one.

DebugRelay is the context and feedback layer between a project and an AI development agent. AI
diagnosis is part of the core product workflow, while the agent may be local, remote, interactive,
or automated. The contract remains independent of a specific model or provider.

## Questions the Product Answers

For every reported problem, a developer should be able to answer:

1. What happened, where, and against which code revision?
2. What evidence is relevant to the problem?
3. What did the development agent conclude, and which code supports that conclusion?
4. What change fixed the problem, and how was the fix verified?
5. Has a sufficiently similar problem already been solved?

## DebugRelay Responsibilities

- issue intake from the web UI, CLI, API, and adapters
- repository and exact revision identity
- evidence validation, redaction, normalization, correlation, and deduplication
- portable, versioned issue bundles
- evidence provenance and access control
- development-agent analysis records
- human-confirmed root causes, fixes, and verification results
- retrieval of similar resolved cases

## Development Agent Responsibilities

- read the issue bundle and authorized source repository
- request additional bounded evidence when necessary
- locate relevant files, symbols, and lines
- separate observed facts from hypotheses
- propose verification steps and code changes
- run checks in an authorized development environment
- report diagnosis, touched code, and verification results

An agent may report a candidate resolution, but only a developer can confirm an issue as resolved.

## Non-Goals

The first version is not:

- a monitoring dashboard or alerting engine
- a log or metrics database
- a replacement for GitHub Issues, Jira, Sentry, Prometheus, Grafana, or Loki
- an embedded chat product or built-in coding-agent runtime
- an autonomous production-remediation system
- a Kubernetes management platform

Those systems may become issue sources or evidence adapters. They are not prerequisites.

## Data Flywheel

Raw log volume is not the flywheel. The valuable record is the reviewed chain:

```text
Problem fingerprint
  -> selected evidence
  -> agent hypotheses
  -> checks and results
  -> confirmed root cause
  -> changed files and fix commit
  -> tests and production verification
```

Initial retrieval should use deterministic fingerprints and text search. Each resolved issue later
becomes both a retrieval candidate and an evaluation case. Model training or fine-tuning is deferred
until there are enough representative, reviewed cases.

Useful quality measures include:

- top-three root-cause accuracy
- accepted evidence rate
- false issue-merge rate
- time to confirmed cause
- whether a matched historical case helped resolve the new issue

## First Reference Project

Dayboard may be used to exercise the first end-to-end workflow because its repository and runtime
are locally available. DebugRelay must still use generic Git, file, HTTP, and runtime adapters; no
core field or service may contain a Dayboard-specific concept.

Related: [Core Workflow](workflow.md) and [MVP Plan](../mvp.md).
