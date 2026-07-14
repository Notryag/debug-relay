# System Architecture

[Wiki Home](../README.md)

## Design Principles

- The versioned issue contract is more stable than any transport or integration.
- The core service stores development cases, not general observability data.
- Source adapters normalize through public ingestion services and never write core tables directly.
- Development agents are external consumers with bounded read and report access.
- PostgreSQL is the source of truth for workflow state and evidence metadata.
- Infrastructure is added only when an accepted use case requires it.

## Logical Architecture

```text
Web / CLI / Webhooks / Source Adapters
                  |
                  v
          FastAPI ingestion API
                  |
                  v
       Evidence processing services
                  |
        +---------+----------+
        |                    |
        v                    v
   PostgreSQL          Artifact storage
        |                    |
        +---------+----------+
                  |
                  v
        REST / Bundle / MCP
                  |
                  v
          Development agent
```

## Planned Components

### API

Owns authentication, project configuration, issue lifecycle, evidence intake, portable exports,
agent reports, resolutions, and search. OpenAPI is generated from the same validated models used by
the service.

### Web

Provides the issue inbox, issue detail, and project settings. It consumes the public API and does
not access PostgreSQL directly.

### CLI

Provides fast manual intake, attachment upload, bundle export, and agent-result import. CLI behavior
must map to public API resources rather than a private database interface.

### Evidence Adapters

Translate source-specific data into the shared Evidence contract. Initial adapters may cover files,
Git, HTTP, and Docker. Kubernetes, issue trackers, error services, and observability platforms are
later adapters.

### Artifact Storage

Stores larger evidence content. Development starts with a local filesystem implementation behind a
storage interface. An S3-compatible implementation can be added without changing issue contracts.

The current backend keeps bounded sanitized evidence bytes in PostgreSQL for transactional intake
and ZIP export. This does not change the boundary for larger artifacts, which remain outside
relational rows.

## Technology Stack

| Layer | Choice |
| --- | --- |
| API | Python, FastAPI, Pydantic |
| Persistence | PostgreSQL, SQLAlchemy, Alembic |
| Initial search | fingerprints, PostgreSQL full-text search, `pg_trgm` |
| Web | Next.js, React, TypeScript |
| CLI | Python, Typer, httpx |
| Contracts | OpenAPI and versioned JSON Schema fixtures |
| Agent access | REST and portable bundles; MCP adapter |
| Application logs | structured JSON with structlog |
| Initial deployment | Docker Compose |

Generate browser and CLI client contracts from OpenAPI or JSON Schema. Do not maintain parallel
handwritten request and response types.

## Persistence

Core relational tables are expected to include:

```text
projects
repositories
issues
evidence
artifacts
agent_analyses
resolutions
issue_links
```

Use explicit columns for stable product fields. JSONB is appropriate for versioned source-specific
extensions, not as a substitute for the domain model. Store artifact metadata and hashes in
PostgreSQL while keeping large content in artifact storage.

## Search and Similarity

The first implementation uses:

- normalized error fingerprints
- exception type and top application stack frames
- PostgreSQL full-text search
- `pg_trgm` fuzzy matching
- explicit project, component, revision, and time filters

Do not add Elasticsearch or a standalone vector database to the MVP. After enough confirmed cases
exist, pgvector may be evaluated against a fixed retrieval test set.

## Background Work

The first manual vertical slice can process bounded evidence synchronously. When automatic
collection or large-artifact processing is introduced, add a durable worker such as arq with Redis.
Do not use in-process background tasks for evidence that must survive a service restart.

## Deployment

The first self-hosted deployment uses Docker Compose for the API. PostgreSQL may be a dedicated
instance or a shared server instance with a separate role and separate DebugRelay databases. Sharing
an application database or schema is not supported. DebugRelay does not need to run in the same
runtime as the project it observes, and Kubernetes support does not require DebugRelay itself to run
in a cluster.

## Go and Kubernetes

Go is not required for the core service. A separate Go collector is justified only by a concrete
need such as:

- distributing a dependency-free host binary
- maintaining high-volume Kubernetes watches and caches
- running a node-level DaemonSet
- implementing a controller with leader election

The first Kubernetes integration should be a read-only API adapter. It collects bounded workload,
event, log, rollout, and image identity evidence and emits the same Evidence contract as every other
adapter.

Related: [Evidence Pipeline](evidence-pipeline.md),
[Project Integration](../integrations/project-integration.md), and [Security](../security.md).
