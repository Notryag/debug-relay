# System Architecture

[Wiki Home](../README.md)

## Design Principles

- Continuous error intake is the primary entry point; manual case creation is a fallback.
- Deterministic code performs authentication, redaction, normalization, grouping, counting, and
  detection before an AI agent sees data.
- DebugRelay stores compact error aggregates and development cases, not an unbounded telemetry copy.
- Source adapters normalize through public ingestion services and never write core tables directly.
- Development agents consume bounded case context and cannot mutate production systems.
- PostgreSQL is the source of truth for receipts, groups, statistics, cases, and verified history.
- Infrastructure is added only when measured volume or durability requires it.

## Logical Architecture

```text
Applications / CI / Webhooks / OTel / Docker / Kubernetes / Sentry
                              |
                              v
                     Collectors and adapters
                              |
                              v
                    Authenticated Event API
                              |
                              v
            validate -> redact -> normalize -> fingerprint
                              |
                              v
        idempotent receipt -> ErrorGroup -> occurrence buckets
                              |
                              v
                       Detection service
                              |
                              v
                  automatic DevelopmentCase
                              |
               +--------------+--------------+
               |                             |
               v                             v
          PostgreSQL                  Artifact storage
               |                             |
               +--------------+--------------+
                              |
                              v
                 REST / Issue Bundle / MCP
                              |
                              v
                    Development agent
                              |
                              v
                 Human-confirmed resolution
```

## Components

### Collectors and Adapters

Collectors continuously read or receive errors from a bounded source and emit the shared
`ErrorEvent` contract. They maintain source cursors or event IDs, retry transient failures, and never
mutate the observed runtime.

The first generic inputs are structured HTTP events and webhooks. Docker log, OpenTelemetry, error
service, CI, and Kubernetes adapters translate their native records into the same contract.

### Event API

Authenticates a project-scoped intake token, validates size and timestamps, redacts sensitive data,
computes a stable fingerprint, rejects duplicate event IDs, and updates aggregate state.

The API does not synchronously call an AI model. An accepted event returns its error-group identity,
updated count, duplicate status, and any automatically opened case ID.

### Grouping and Statistics

Events are grouped by project, environment, component, and deterministic fingerprint. PostgreSQL
stores aggregate count, first and last seen timestamps, latest release identity, a sanitized sample,
and one-minute occurrence buckets. Receipts retain only the minimum metadata needed for idempotency
and audit.

### Detection Service

Evaluates deterministic policies against group state. The first implementation opens a case for a
new `error` or `critical` group when the event identifies a registered repository and immutable
commit. Later policies add rate changes, recurrences, and release regressions.

Detection remains separable from ingestion so higher volumes can move evaluation to a durable worker
without changing event or case contracts.

### Case API

Owns the existing issue lifecycle, selected evidence, portable exports, agent reports, human
resolution, and similar-case retrieval. An automatically created case and a manual fallback case use
the same downstream service.

### Web

The first screen is an error-group inbox with counts, trends, affected revisions, detection status,
and active case state. Case detail supports evidence review, agent analysis, and resolution.

### CLI

The CLI is an operational and agent adapter. Its primary monitoring role is inspecting groups,
exporting a detected case, reporting analysis, and confirming reviewed resolutions. Raw JSON case
creation remains a low-level debugging fallback, not the normal developer workflow.

## Technology Stack

| Layer | Choice |
| --- | --- |
| API and processing | Python, FastAPI, Pydantic |
| Persistence | PostgreSQL, SQLAlchemy, Alembic |
| Initial aggregation | PostgreSQL receipts, groups, and one-minute buckets |
| Initial search | fingerprints, PostgreSQL full-text search, `pg_trgm` |
| Web | Next.js, React, TypeScript |
| CLI | Python, Typer, httpx |
| Contracts | OpenAPI and versioned JSON Schema |
| Agent access | REST and portable bundles; MCP adapter later |
| Application logs | structured JSON with structlog |
| Initial deployment | Docker Compose |

## Persistence

Core relational tables include:

```text
projects
repositories
error_event_receipts
error_groups
error_occurrence_buckets
issues                    # current storage name for DevelopmentCase
evidence
agent_analyses
resolutions
```

Stable product fields use explicit columns. JSONB is limited to bounded source, release, correlation,
and sanitized sample extensions. Large artifacts remain outside relational rows.

Receipt and bucket retention is shorter than case and resolution retention. Raw telemetry remains in
the source system.

## Concurrency and Delivery

- Event IDs are unique per project and provide at-least-once delivery safety.
- Group updates are serialized by a transaction-scoped advisory lock on group identity.
- Receipt, count, bucket, and automatic case creation commit in one PostgreSQL transaction.
- A duplicate delivery returns the original group and case identity without incrementing counts.
- Collector retries use bounded exponential backoff and preserve the original event ID.

The first slice processes one bounded event synchronously. A durable worker and queue are introduced
only when measured ingestion volume makes synchronous detection insufficient. In-process background
tasks are not used for state that must survive restarts.

## Deployment

The first self-hosted deployment uses Docker Compose. PostgreSQL may be a dedicated instance or a
shared server instance with a separate role and separate DebugRelay databases. Sharing another
application's database or schema is unsupported.

DebugRelay does not need to run beside the observed project. Collectors need only outbound access to
the event API, and Kubernetes support does not require the core service to run in a cluster.

## Go and Kubernetes

Go is not required for the core service. A separate Go collector becomes justified only by a
concrete distribution or watch requirement such as a dependency-free host binary, high-volume
Kubernetes watches, a node DaemonSet, or controller leader election.

The first Kubernetes adapter is read-only and emits the same `ErrorEvent` or bounded evidence
contract as every other source.

Related: [Evidence Pipeline](evidence-pipeline.md),
[Project Integration](../integrations/project-integration.md), and [Security](../security.md).
