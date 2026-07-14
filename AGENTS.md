# Agent Notes

These instructions apply to the entire DebugRelay repository.

## Start Here

- Begin every task at `docs/README.md` and follow its task-based reading table.
- Read `docs/product/vision.md` and `docs/mvp.md` before changing product scope.
- Read `docs/contracts/issue-bundle-v1.md` before changing public data contracts.
- Read `docs/security.md` before changing evidence collection, storage, export, authentication, or
  repository access.
- The backend vertical slice is implemented: Issue Bundle v1, PostgreSQL persistence, scoped tokens,
  evidence redaction, REST resources, ZIP export, and integration tests. The CLI and web application
  have not started. Keep new work within the next routed MVP stage.

## Product Invariants

- DebugRelay is a generic developer problem-context and resolution system.
- Dayboard is only a possible reference integration; core concepts must never depend on it.
- AI development-agent diagnosis is required in the core workflow, but the agent runtime may remain
  external to DebugRelay.
- DebugRelay is model- and provider-agnostic; no core contract may depend on one model vendor.
- REST, OpenAPI, and versioned JSON Schema are canonical. CLI and MCP are adapters.
- Source code stays in an authorized repository or workspace unless explicitly attached.
- Evidence is validated, bounded, and redacted before storage and export.
- Agent facts and hypotheses must cite evidence IDs or source-code locations.
- Only a developer can confirm that an issue is resolved.
- Monitoring tools, issue trackers, Docker, and Kubernetes are optional evidence sources.

## Scope Discipline

- Preserve the small issue lifecycle: `open`, `analyzing`, and `resolved`.
- Prefer a complete issue-to-resolution vertical slice over broad integration coverage.
- Do not add a monitoring dashboard, alert engine, log database, embedded chat product,
  provider-specific model runtime, autonomous remediation, or Kubernetes operator to the MVP.
- Do not add Elasticsearch, Kafka, a standalone vector database, or a second implementation
  language without measured need.
- Go is reserved for a future distributed collector or Kubernetes controller when its deployment or
  watch semantics justify it; the core service remains Python.

## Documentation

- Keep `README.md` short and use `docs/README.md` as the wiki home.
- Put each durable concept on its routed wiki page instead of duplicating it across pages.
- Update navigation when adding, moving, or deleting a page.
- Use relative Markdown links within the repository.
- Keep examples free of real credentials, private repository URLs, and production data.
- Default to ASCII unless an existing document establishes another character set.

## Planned Engineering Conventions

- API: Python, FastAPI, Pydantic, SQLAlchemy, Alembic, and PostgreSQL.
- Web: Next.js, React, and TypeScript.
- CLI: Python, Typer, and httpx.
- Generate client types from OpenAPI or JSON Schema; do not maintain duplicate handwritten
  contracts.
- PostgreSQL is the source of truth. Use JSONB only for source-specific extensions, not for all core
  fields.
- Store large artifacts behind a storage abstraction; do not put arbitrary blobs in relational
  rows.
- Use deterministic fingerprints and PostgreSQL search before adding embeddings.
- Use durable workers only when asynchronous collection is introduced; do not use in-process
  background tasks for evidence that must not be lost.

## Verification

- Contract changes require schema fixtures and compatibility tests.
- Redaction changes require positive and negative secret-leak fixtures.
- Persistence behavior requires PostgreSQL-backed tests.
- UI workflow changes require focused component tests and one end-to-end issue flow.
- Adapter tests must verify access scope, size limits, provenance, and normalization.

## Git Safety

- Preserve user changes and unrelated work in a dirty worktree.
- Never commit secrets or captured production evidence.
- Do not rewrite history or use destructive reset commands without explicit approval.
