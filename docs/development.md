# Backend Development

[Wiki Home](README.md)

## Current Backend

The first backend vertical slice is implemented. It persists projects, repository snapshots,
issues, sanitized evidence, AI development-agent analyses, and human-confirmed resolutions in
PostgreSQL. It can export a validated Issue Bundle v1 ZIP and retrieve similar resolved issues.

The backend is suitable for local development and acceptance testing. It is not ready for public
internet exposure because human session authentication, request-rate limiting, idempotent intake,
and large-artifact storage are not implemented yet.

## Prerequisites

- Python 3.11 or newer
- uv
- PostgreSQL 17 with the `pg_trgm` extension available
- Docker with Compose when running the API container

## Database Isolation

DebugRelay may share a PostgreSQL server instance with another local project, but it uses a separate
role and separate databases. It must never share another application's database or schema.

The current workspace uses:

```text
role: debugrelay
development database: debugrelay
test database: debugrelay_test
```

Create equivalent resources as a PostgreSQL administrator, substituting a strong generated password:

```sql
CREATE ROLE debugrelay LOGIN PASSWORD '<generated-password>'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE DATABASE debugrelay OWNER debugrelay;
CREATE DATABASE debugrelay_test OWNER debugrelay;
```

Sharing an instance saves resources but also shares its availability and capacity. Back up and
restore the DebugRelay database independently, and keep role privileges isolated.

## Local Environment

Create a local `.env` from `.env.example` and replace every placeholder. Real credentials remain in
`.env` and are ignored by Git.

For a host process:

```text
DEBUGRELAY_ENV=local
DEBUGRELAY_ADMIN_TOKEN=<at-least-32-random-characters>
DATABASE_URL=postgresql+asyncpg://debugrelay:<password>@127.0.0.1:5432/debugrelay
```

Install dependencies and apply migrations:

```bash
uv sync --dev
uv run alembic upgrade head
```

Run the API on the host:

```bash
uv run uvicorn debugrelay.main:app --host 127.0.0.1 --port 8010
```

The API documentation is available at `http://127.0.0.1:8010/docs`.

The source checkout also exposes the REST-backed CLI:

```bash
uv run debugrelay --help
```

See [Command-Line Interface](cli.md) for configuration, token scopes, examples, and exit codes.

## Docker API

The Compose file runs only the API. It connects to an existing PostgreSQL container through an
external Docker network instead of starting a second database server.

Configure:

```text
DEBUGRELAY_POSTGRES_NETWORK=<network-containing-postgres>
DEBUGRELAY_DOCKER_DATABASE_URL=postgresql+asyncpg://debugrelay:<password>@postgres:5432/debugrelay
```

The database container must be reachable as `postgres` on that network. Then run:

```bash
docker compose build api
docker compose up -d api
docker compose ps
curl -fsS http://127.0.0.1:8010/health
```

The current workspace network is `dayboard_default`; this is local deployment configuration, not a
DebugRelay product dependency.

## Authentication Scopes

All `/api` resources require a bearer token.

- admin token: configured through `DEBUGRELAY_ADMIN_TOKEN`; creates projects and confirms resolution
- intake token: generated once when a project is created; creates issues and appends evidence only
- agent token: generated once when a project is created; reads issue context, downloads bundles, and
  reports analysis

Project tokens are stored only as SHA-256 hashes. They are high-entropy bearer tokens and are shown
only in the project-creation response.

The fallback `debugrelay-local-admin` token exists only for loopback-bound local development. A
production configuration refuses to start without an explicit admin token of at least 32 characters.

## Implemented Resources

```text
GET  /health
POST /api/projects
GET  /api/projects/{project_id}
POST /api/issues
GET  /api/issues
GET  /api/issues/{issue_id}
POST /api/issues/{issue_id}/evidence
GET  /api/issues/{issue_id}/evidence
GET  /api/issues/{issue_id}/evidence/{evidence_id}/content
GET  /api/issues/{issue_id}/bundle
GET  /api/issues/{issue_id}/similar
POST /api/issues/{issue_id}/analyses
POST /api/issues/{issue_id}/resolve
```

Issue creation requires one registered repository snapshot, one immutable commit, and initial anchor
evidence. Posting an analysis changes the issue to `analyzing`. Only the admin scope can create the
human-confirmed resolution and move the issue to `resolved`.

## Evidence Storage and Redaction

The MVP stores bounded sanitized evidence bytes in PostgreSQL so issue creation and export stay
transactional. Large artifacts remain deferred to the storage abstraction described in the
architecture.

Before storage, the service redacts sensitive JSON keys and common secret forms in text, including
authorization headers, bearer tokens, credential assignments, URL credentials, and private keys.
It computes byte size and SHA-256 only after redaction. Source selectors, attributes, issue text,
analysis output, and resolution text also pass through deterministic sanitization.

Redaction reduces accidental disclosure but is not a proof that arbitrary production data is safe.
Projects still need allowlisted sources and tests for their own sensitive fields.

## Tests

Tests refuse a database name that does not end in `_test`.

```bash
TEST_DATABASE_URL=postgresql+asyncpg://debugrelay:<password>@127.0.0.1:5432/debugrelay_test \
  uv run pytest -q
uv run ruff check src alembic tests
uv run ruff format --check src alembic tests
```

The API tests use real migrations and PostgreSQL. They truncate only the configured test database.
They cover token scope, token hashing, cross-project isolation, secret redaction, evidence access,
analysis citations, human-only resolution, ZIP export, schema validation, and similar-case retrieval.
CLI tests cover REST mapping, bearer-token handling, local size limits, path-free attachment
provenance, timestamp normalization, bounded downloads, and stable error exits.

Related: [System Architecture](architecture/overview.md), [Command-Line Interface](cli.md),
[Security](security.md), and [Issue Bundle v1](contracts/issue-bundle-v1.md).
