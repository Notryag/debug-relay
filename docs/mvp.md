# MVP Plan

[Wiki Home](README.md)

## Goal

Prove that a problem can be recorded once, handed to a real AI development agent with enough context
to inspect the correct source revision, and returned as a human-confirmed reusable case.

The agent runtime may remain external to DebugRelay, but an AI diagnosis round trip is required for
MVP acceptance. The core contract must not depend on one model or provider.

## Current Progress

- Complete: Issue Bundle v1 Draft 2020-12 JSON Schema
- Complete: minimal, exception, and resolved portable examples
- Complete: schema, reference-integrity, and content-integrity contract tests
- Complete: PostgreSQL domain storage and initial migration
- Complete: scoped project tokens, evidence redaction, REST workflow, and bundle export
- Complete: PostgreSQL integration and security tests
- Complete: CLI create, show, attach, export, analysis, resolution, and similar-case commands
- Next: issue inbox, issue detail, and project settings web views

## Vertical Slice

1. Register a project and one repository mapping.
2. Create an issue manually from the web or CLI.
3. Record the exact source revision and attach bounded evidence.
4. Sanitize, deduplicate, and export Issue Bundle v1.
5. Let an external development agent read the bundle and authorized repository.
6. Accept structured analysis containing evidence references and code locations.
7. Let a developer confirm root cause, fix revision, checks, and outcome.
8. Retrieve the resolved issue from a similar sample problem.

## Required UI

- issue inbox
- issue detail and evidence views
- project and repository settings
- issue creation
- analysis review and resolution confirmation

There is no dashboard, chat page, or separate knowledge-base page in the MVP.

## Required Interfaces

- versioned Issue Bundle JSON Schema and fixtures
- REST resources for projects, issues, evidence, analyses, and resolutions
- CLI create, show, attach, export, report-analysis, and resolve commands

MCP is useful but follows the stable REST and bundle contract. It is not required to prove the first
file-based agent handoff.

## Acceptance Criteria

- one real AI development agent completes an analysis round trip
- the same issue bundle can be consumed without a provider-specific field
- every handed-off issue identifies an immutable source revision
- an exported bundle is readable without database access
- configured secret fixtures never appear in stored or exported evidence
- agent facts and hypotheses reference evidence IDs or source locations
- only a developer can confirm resolution
- a resolution records root cause, fix revision, verification command or procedure, and result
- a repeated sample problem retrieves its prior resolved case
- no core schema or service contains a Dayboard-specific field

## First Reference Case

Dayboard is a suitable first dogfood project because its repository and Docker Compose runtime are
locally available. The acceptance case should use only generic Git, file, HTTP, and Docker evidence
adapters.

The first case should include:

- one reproducible application error
- one exact repository revision
- a small stack trace or log sample
- agent analysis citing at least one evidence item and one source location
- a real or fixture fix revision
- a focused verification command and result

## Deferred Scope

- automatic model invocation and model-provider budgets
- built-in coding-agent orchestration
- monitoring dashboards and alert routing
- high-volume log or metrics retention
- autonomous code merge, deployment, rollback, or remediation
- multi-tenant SaaS administration
- Kubernetes Operator and node-level collector
- cross-project embedding search and fine-tuning
- replacement of existing issue trackers

## Delivery Stages

1. Complete: finalize Issue Bundle v1 JSON Schema and representative fixtures.
2. Complete: implement PostgreSQL domain storage and REST resources.
3. Complete: add the CLI and portable API export.
4. Next: build the issue inbox, issue detail, and project settings pages.
5. Complete one real AI development-agent analysis and resolution round trip.
6. Complete: add deterministic similar-case retrieval.
7. Add generic Git, file, Docker, webhook, and HTTP evidence adapters.
8. Add MCP and Kubernetes adapters only after the core contract is stable.

## Remaining Acceptance Decisions

- the first external development agent used for acceptance testing
- repository-locator to authorized-workspace mapping
- retention policy beyond the current bounded sanitized-evidence MVP
- the first end-to-end acceptance issue

Related: [Product Vision](product/vision.md), [System Architecture](architecture/overview.md), and
[Issue Bundle v1](contracts/issue-bundle-v1.md).
