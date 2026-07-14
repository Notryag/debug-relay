# Issue Bundle v1

[Wiki Home](../README.md)

## Role

Issue Bundle v1 is the stable, portable contract between DebugRelay, a developer, and a development
agent. REST, CLI, file export, and MCP must represent the same concepts.

The exact JSON Schema and fixtures are the first implementation deliverable. This page defines the
design requirements before those machine-readable files exist.

## Version Identity

The proposed schema identifier is:

```text
debugrelay.issue-bundle/v1
```

Readers must reject unsupported major versions. Additive optional fields may evolve within v1;
required-field removal or semantic changes require a new major version.

## Required Fields

- `schema_version`
- `issue_id`
- `project_id`
- `environment`
- `component`
- `occurred_at` in UTC
- `summary`
- `expected`
- `actual`
- `reproduction`
- at least one repository locator
- an immutable `commit_sha` or equivalent source revision
- `evidence_refs`
- `redaction_status`

## Recommended Fields

- `service.name`
- `service.version`
- `trace_id`
- `span_id`
- `request_id`
- `deployment_id`
- `image_digest`
- `source_map_revision`
- configuration or feature-flag fingerprints, never secret values

Field names should align with OpenTelemetry semantic attributes and W3C Trace Context where those
standards already define a concept. Full OpenTelemetry adoption is not an integration requirement.

## Minimal Shape

```json
{
  "schema_version": "debugrelay.issue-bundle/v1",
  "issue": {
    "id": "ISSUE-123",
    "project_id": "example-project",
    "environment": "production",
    "component": "api",
    "occurred_at": "2026-07-14T01:00:00Z",
    "summary": "Request fails while saving an item",
    "expected": "The item is saved",
    "actual": "The API returns an error",
    "reproduction": ["Submit a valid item"]
  },
  "repositories": [
    {
      "role": "primary",
      "locator": "https://example.invalid/example/project.git",
      "commit_sha": "0123456789abcdef0123456789abcdef01234567"
    }
  ],
  "evidence": [
    {
      "id": "EVIDENCE-1",
      "kind": "exception",
      "content_ref": "evidence/exception-1.json",
      "redaction_status": "sanitized"
    }
  ]
}
```

Example values must remain fictional and free of real credentials or private repository locations.

## Portable Layout

```text
manifest.json
issue.json
repositories.json
evidence/
artifacts/
analyses.json
resolution.json
summary.md
```

`manifest.json` lists every file, media type, size, and content hash. `summary.md` is a generated
human- and agent-readable entry point; JSON remains canonical.

Source code is not copied into a bundle by default. The bundle identifies the repository and exact
revision, and the agent reads code from an explicitly authorized workspace or source provider.

## Analysis Contract

An agent analysis records:

- observed facts with evidence or source citations
- ranked hypotheses, each clearly marked as unconfirmed
- relevant repositories, files, symbols, and line locations
- missing information
- proposed verification steps
- proposed changes and affected tests
- commands run and their outcomes, when applicable

## Resolution Contract

A human-confirmed resolution records:

- root cause and its applicable conditions
- accepted analysis or corrected explanation
- changed files and fix revision
- verification command or procedure
- verification result and time
- whether the fix was observed in the affected environment

Related: [Core Workflow](../product/workflow.md),
[Agent Interface](../integrations/agent-interface.md), and [MVP Plan](../mvp.md).
