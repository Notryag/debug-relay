# Issue Bundle v1

[Wiki Home](../README.md)

## Status

Issue Bundle v1 has an executable Draft 2020-12 JSON Schema, portable examples, and contract tests:

- [JSON Schema](../../schemas/issue-bundle/v1/schema.json)
- [Minimal report](../../examples/issue-bundles/minimal/bundle.json)
- [Exception with correlated change](../../examples/issue-bundles/exception/bundle.json)
- [AI analysis and confirmed resolution](../../examples/issue-bundles/resolved/bundle.json)
- [Contract tests](../../tests/contracts/test_issue_bundle_schema.py)

The schema identifier is:

```text
urn:debugrelay:schema:issue-bundle:v1
```

## Role

Issue Bundle v1 is the stable, portable downstream contract between an automatically detected or
manually recorded development case, a developer, and an AI development agent. Raw runtime events and
error-group statistics are upstream monitoring concepts and are not copied wholesale into a bundle.
REST, CLI, file export, and MCP must represent the same case concepts rather than inventing
provider-specific payloads.

The contract carries three distinct layers:

1. problem identity and sanitized evidence
2. AI agent facts, hypotheses, source locations, and checks
3. human-confirmed root cause, fix revisions, and verification

An AI analysis does not resolve an issue. The `resolved` state requires both an analysis and a
human-confirmed resolution containing at least one passed verification.

## Validation Model

Validation has two layers.

### JSON Schema

The schema enforces:

- the exact v1 schema identifier
- Draft 2020-12 structure and closed object fields
- UTC timestamps ending in `Z`
- one immutable primary Git revision
- sanitized bundle and evidence status
- bounded arrays, strings, evidence sizes, and artifact sizes
- file-backed evidence with safe relative paths and byte-level integrity metadata
- facts and hypotheses with citations
- resolved-state analysis and resolution requirements
- human confirmation and passed verification for a resolution

Unknown top-level and nested fields are rejected. Provider-specific data must not leak into the
portable core contract.

### Semantic and File Integrity

Some invariants require cross-record or filesystem checks beyond JSON Schema. The contract tests
enforce:

- unique repository, evidence, artifact, and analysis IDs
- resolvable issue, citation, derivation, artifact, and resolution references
- safe relative content paths contained within the bundle directory
- existing referenced files
- exact byte sizes and SHA-256 hashes
- valid source repository references and ordered source line ranges
- ordered evidence time ranges
- unique hypothesis ranks within an analysis

The application validator must implement the same checks before accepting or exporting a bundle.

## Versioning

Readers reject unsupported major versions. Additive optional fields may evolve within v1 when they
do not change existing semantics. Removing required fields, changing meanings, loosening security
guarantees, or changing canonical content hashing requires a new major version.

The canonical value in `bundle.json` is:

```json
{
  "schema_version": "debugrelay.issue-bundle/v1"
}
```

## Portable Layout

`bundle.json` is the single authoritative metadata document. Evidence and artifacts may be stored as
referenced files:

```text
bundle.json
evidence/
artifacts/
summary.md
```

`summary.md` is an optional generated entry point for people and file-oriented agents. JSON remains
canonical. Every referenced file records its relative path, media type, byte size, and SHA-256 hash
inside `bundle.json`.

Source code is not copied into a bundle by default. The bundle identifies a repository and exact
revision; the agent reads code from an explicitly authorized workspace or source provider.

## Top-Level Contract

Every bundle contains:

- `schema_version`: exact v1 contract name
- `generated_at`: UTC bundle-generation time
- `redaction_status`: `sanitized` in v1
- `issue`: symptom, state, correlation, and anchor evidence references
- `repositories`: at least one repository and exactly one primary repository
- `evidence`: bounded evidence metadata and content references

Optional top-level collections are:

- `artifacts`: larger screenshots, recordings, trace exports, source maps, or archives
- `analyses`: structured AI development-agent output
- `resolution`: human-confirmed root cause, fixes, and verification

## Issue Identity

Every issue records:

- stable issue, project, environment, and component IDs
- `open`, `analyzing`, or `resolved` state
- UTC occurrence time
- summary, expected behavior, actual behavior, and reproduction steps
- one or more anchor evidence references

Optional identity includes service name and version, normalized fingerprint, labels, W3C trace and
span IDs, request or job IDs, deployment identity, image digest, source-map revision, and
configuration fingerprints.

Configuration may be represented only by key name and fingerprint. Secret configuration values do
not belong in the bundle.

## Repository Identity

Every repository entry has:

- stable repository ID
- `primary` or `related` role
- URI locator
- lowercase 40- or 64-character immutable Git object ID

A branch may be included as advisory context but never replaces the immutable commit. Local
workspace paths are authorization configuration and are not portable bundle fields.

## Evidence

Each evidence record contains:

- stable ID, kind, and short summary
- one observation time or bounded observation range
- collection time
- source adapter, locator, and optional selector or query
- relationship to the anchor event
- media type, byte size, and SHA-256 hash
- a safe relative `content_ref`
- `sanitized` status and redaction-policy version
- optional derivation, artifact, and source-specific attributes

Initial evidence kinds cover user reports, exceptions, logs, requests, runtime state, changes,
deployments, tests, traces, metrics, and an explicit `other` escape hatch.

## AI Analysis

An analysis records:

- agent name and optional runtime metadata
- observed facts with evidence or source citations
- ranked hypotheses marked `unconfirmed`, `supported`, or `rejected`
- verification steps and their results
- missing information
- proposed changes with repository and source locations
- checks and their evidence references

Provider and model names are optional metadata. No provider-specific field is required or allowed in
the portable contract.

## Resolution

A resolution records:

- `human_confirmed: true`
- human actor and confirmation time
- the accepted analysis ID
- confirmed root cause and applicable conditions
- one or more repository fix commits and changed files
- one or more passed verification records
- whether the fix was observed in the affected environment

Agent credentials may submit an analysis or candidate resolution, but only human-authorized product
logic may create this confirmed resolution object.

## Validate Locally

```bash
uv sync --dev
uv run pytest -q tests/contracts
```

The test suite validates the schema itself, all three examples, content hashes and references, and a
set of deliberately invalid mutations.

Related: [Core Workflow](../product/workflow.md),
[Agent Interface](../integrations/agent-interface.md), and [MVP Plan](../mvp.md).
