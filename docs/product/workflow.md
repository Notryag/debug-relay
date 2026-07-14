# Core Workflow and Domain Model

[Wiki Home](../README.md)

## Workflow

```text
Project, developer, CI, or webhook
                |
                v
          Create an issue
                |
                v
  Sanitize and organize evidence
                |
                v
       Build Issue Bundle v1
                |
                v
  Development agent reads bundle
                |
                v
 Diagnosis, code locations, checks
                |
                v
 Developer confirms and applies fix
                |
                v
 Root cause, commit, and verification
                |
                v
       Reusable resolved case
```

The first complete implementation should support this entire vertical flow before adding broad
automatic collection.

## Issue Lifecycle

The MVP has three states:

- `open`: the problem exists and may still need context
- `analyzing`: a development agent or developer is actively investigating
- `resolved`: a developer confirmed the root cause, fix, and verification result

Agent output alone cannot transition an issue to `resolved`. Reopening a resolved issue returns it
to `open` while preserving the earlier resolution history.

## Core Concepts

### Project

Project identity, repositories, allowed workspaces, evidence adapters, intake credentials, and
redaction policy.

### Repository

A repository locator, its allowed local or remote access mapping, and immutable revision metadata.
An issue may reference multiple repositories, but one should be identified as primary.

### Issue

The reported symptom, expected behavior, actual behavior, reproduction steps, occurrence context,
state, and exact source revision.

### Evidence

A sanitized, attributable observation related to an issue. Evidence is bounded and retains its
source, collection time, observed time range, query or selector, content hash, and redaction status.

### Artifact

A larger file such as a screenshot, trace export, source map reference, or compressed log sample.
Artifact metadata remains relational while content is stored behind an artifact storage interface.

### AgentAnalysis

An agent's observed facts, ranked hypotheses, cited evidence, source-code locations, missing
information, and proposed verification steps.

### Resolution

The developer-confirmed root cause, changed files, fix revision, verification command or procedure,
result, and applicable conditions.

## Invariants

- Every issue identifies an immutable source revision before agent handoff.
- Facts cite evidence IDs or source-code locations.
- Hypotheses are explicitly marked and remain distinct from facts.
- Evidence is not silently mutated after agent handoff; derived or corrected evidence is added with
  provenance.
- A resolution records both the fix and how it was verified.
- Similarity does not merge issue history automatically; a developer can reject a bad match.

Related: [Issue Bundle v1](../contracts/issue-bundle-v1.md),
[Evidence Pipeline](../architecture/evidence-pipeline.md), and
[Development Agent Interface](../integrations/agent-interface.md).
