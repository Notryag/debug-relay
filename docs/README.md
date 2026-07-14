# DebugRelay Wiki

This wiki is the source of truth for DebugRelay product and engineering decisions. The root
`README.md` is only the repository entry point.

## Current Status

DebugRelay has completed its first backend vertical slice and CLI: Issue Bundle v1, PostgreSQL
persistence, scoped tokens, evidence redaction, REST resources, ZIP export, similar-case retrieval,
and file-oriented developer and agent commands. The web application and real-agent acceptance case
are next; public production exposure remains deferred.

## Read by Task

| Task | Read |
| --- | --- |
| Understand the product | [Product Vision](product/vision.md) |
| Change issue states or domain concepts | [Core Workflow and Domain Model](product/workflow.md) |
| Design or implement the UI | [Web Application](product/web-application.md) |
| Choose services, storage, or runtime | [System Architecture](architecture/overview.md) |
| Collect, filter, or rank evidence | [Evidence Pipeline](architecture/evidence-pipeline.md) |
| Change the portable contract | [Issue Bundle v1](contracts/issue-bundle-v1.md) |
| Connect a project or runtime | [Project Integration](integrations/project-integration.md) |
| Connect a development agent | [Development Agent Interface](integrations/agent-interface.md) |
| Use or change the CLI | [Command-Line Interface](cli.md) |
| Change auth, redaction, or access | [Security](security.md) |
| Run or change the backend | [Backend Development](development.md) |
| Plan implementation or acceptance | [MVP Plan](mvp.md) |

## Recommended Reading Paths

Product review:

1. [Product Vision](product/vision.md)
2. [Core Workflow and Domain Model](product/workflow.md)
3. [Web Application](product/web-application.md)
4. [MVP Plan](mvp.md)

Core implementation:

1. [System Architecture](architecture/overview.md)
2. [Issue Bundle v1](contracts/issue-bundle-v1.md)
3. [Evidence Pipeline](architecture/evidence-pipeline.md)
4. [Security](security.md)
5. [Backend Development](development.md)
6. [MVP Plan](mvp.md)

Integration implementation:

1. [Project Integration](integrations/project-integration.md)
2. [Evidence Pipeline](architecture/evidence-pipeline.md)
3. [Development Agent Interface](integrations/agent-interface.md)
4. [Command-Line Interface](cli.md)
5. [Security](security.md)

## Product Boundary

DebugRelay owns problem context, evidence provenance, AI development-agent handoff, and verified
resolution history. It does not own monitoring, alert routing, source control, issue tracking, a
provider-specific model runtime, or production remediation.

## Documentation Rules

- Each durable concept has one canonical page.
- Other pages link to that definition instead of copying it.
- Contract examples are versioned and testable once implementation begins.
- Decisions that change product boundaries must update the Product Vision and MVP Plan together.
