# Project Integration

[Wiki Home](../README.md)

## Principle

A project can start manually and add richer evidence later. DebugRelay must not require a monitoring
stack, runtime agent, or Kubernetes deployment before it can create a useful issue bundle.

Every source adapter converts source-specific input into the shared Issue and Evidence contracts.
Adapters do not define new core workflow states or write database tables directly.

## Integration Levels

### Level 0: Manual

- create an issue in the web UI or CLI
- provide a repository and exact revision
- enter expected behavior, actual behavior, and reproduction steps
- paste a bounded error or stack trace
- attach bounded files

### Level 1: Basic

- report structured JSON errors through the API or a webhook
- include stable project, environment, component, and release identity
- provide repository mapping and a bounded log source

### Level 2: Correlated

- propagate trace, request, task, and job identifiers
- report deployment, migration, and image metadata
- expose read-only runtime and health evidence adapters

### Level 3: Deep

- provide OpenTelemetry context, frontend source maps, Kubernetes evidence, or domain-specific
  diagnostic probes
- allow bounded follow-up evidence queries from an authorized development agent

## Minimum Project Standard

Every integrated project provides:

- a stable project ID
- environment and component identity
- UTC timestamps
- at least one repository locator
- an exact source revision for every issue handed to an agent
- scoped intake credentials
- per-source payload and attachment limits
- a project redaction and retention policy

Configuration may be represented by key name, revision, or fingerprint. Secret values must not be
collected.

## Adapter Contract

An adapter must:

1. authenticate its source or caller
2. map source identity to one configured project
3. enforce source-specific request and byte limits
4. emit validated Issue or Evidence input
5. preserve source locator, query or selector, time range, and content hash
6. report partial collection and permission failures explicitly
7. avoid runtime mutation

Adapters should be replaceable without changing an existing issue bundle's meaning.

## Initial Adapters

The first useful set is:

- manual web and CLI input
- local file attachment
- Git repository and revision metadata
- bounded HTTP evidence fetch
- Docker container identity, state, and selected logs

Sentry, GitHub, GitLab, CI systems, OpenTelemetry, Loki, and similar products can later submit or
supply evidence through adapters.

## Kubernetes Adapter

Kubernetes can standardize runtime evidence, but it does not identify faulty source code without
release metadata. Workloads should expose or annotate:

- repository locator
- commit SHA
- service name and version
- image digest
- deployment identity and time
- source-map revision for frontend artifacts when applicable

The initial adapter may read bounded data for pods, pod logs, events, deployments, ReplicaSets,
Jobs, and rollout state. Its service account must not read Secrets, execute inside pods, mutate
resources, or delete resources.

Kubernetes evidence can explain symptoms such as restart, failed probe, scheduling failure,
eviction, rollout failure, or out-of-memory termination. The source revision and application
evidence are still required for code-level diagnosis.

## Source Maps and Build Metadata

Frontend projects should map every deployed asset revision to an immutable source revision and its
matching source maps. Containerized projects should map image digest to repository and commit SHA.
These mappings belong to release metadata, not to inference from mutable tags such as `latest`.

Related: [Issue Bundle v1](../contracts/issue-bundle-v1.md),
[Evidence Pipeline](../architecture/evidence-pipeline.md), and [Security](../security.md).
