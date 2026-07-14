# Development Agent Interface

[Wiki Home](../README.md)

## Boundary

The development agent is external to DebugRelay. Deterministic monitoring opens a development case
and DebugRelay packages selected context; the agent inspects authorized source code, analyzes the
case, performs development checks, and reports structured results.

DebugRelay does not prescribe a model provider or agent runtime. A local CLI-based agent, an IDE
agent, a remote service, and a file-only workflow must all be able to consume the same issue.

## Canonical Interface

REST, OpenAPI, and the versioned Issue Bundle JSON Schema are canonical. CLI and MCP interfaces are
adapters over those resources.

Implemented REST resources:

```text
POST /api/events
GET  /api/error-groups
GET  /api/error-groups/{group_id}
POST /api/issues
GET  /api/issues/{issue_id}
POST /api/issues/{issue_id}/evidence
GET  /api/issues/{issue_id}/bundle
GET  /api/issues/{issue_id}/evidence
GET  /api/issues/{issue_id}/similar
POST /api/issues/{issue_id}/analyses
POST /api/issues/{issue_id}/resolve
```

Agent report and human-only resolution confirmation use distinct token scopes.

## CLI

The implemented command surface is:

```text
debugrelay project create PROJECT_JSON
debugrelay project show PROJECT_ID
debugrelay groups list --project PROJECT_ID
debugrelay groups show GROUP_ID
debugrelay issue create ISSUE_JSON
debugrelay issue list --project PROJECT_ID
debugrelay issue show ISSUE_ID
debugrelay issue export ISSUE_ID
debugrelay issue attach ISSUE_ID PATH
debugrelay issue report-analysis ISSUE_ID RESULT_JSON
debugrelay issue resolve ISSUE_ID RESOLUTION_JSON
```

The CLI is the simplest portable handoff. The normal path begins with a detected group and its
automatically opened case; manual JSON case creation is only an adapter-debugging fallback. An
exported bundle remains usable when the agent has no live access to the server. Configuration,
scopes, and limits are documented in the [Command-Line Interface](../cli.md).

## MCP Adapter

An MCP server may expose:

- `get_issue`
- `search_evidence`
- `get_artifact`
- `find_similar_issues`
- `report_diagnosis`
- `report_verification`
- `attach_fix`

Each call enforces project, issue, source, time, item-count, and byte scope on the server. MCP must
not be the only supported agent path.

## Agent Analysis

The agent reports:

- facts with evidence IDs or source-code citations
- ranked and explicitly unconfirmed hypotheses
- relevant repository, revision, files, symbols, and lines
- missing information and bounded evidence requests
- verification steps and their results
- proposed code changes and affected tests

Free-form Markdown may accompany the result, but structured fields are canonical and power the
case library.

## Agent Access

- The automatically opened case identifies repository locators and exact revisions.
- A local deployment maps configured repositories to allowlisted workspace roots.
- A remote deployment uses scoped source-provider access or a prepared workspace.
- Runtime events and cases do not grant access to an arbitrary filesystem path.
- The agent receives no production shell, Kubernetes exec, database write, or deployment capability
  from DebugRelay.
- Agent write credentials can report analysis but cannot confirm resolution.

## Follow-Up Evidence

An agent begins with the summary and selected evidence. If context is insufficient, it requests a
narrow source query through DebugRelay. The server applies redaction and budgets before returning
new evidence and records the query in the case history.

Related: [Issue Bundle v1](../contracts/issue-bundle-v1.md),
[Core Workflow](../product/workflow.md), and [Security](../security.md).
