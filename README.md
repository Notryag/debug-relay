# DebugRelay

DebugRelay captures a software problem, packages the relevant context for a development agent, and
records the verified fix as a reusable case.

> Make every debugging session useful to the next one.

DebugRelay is model-agnostic. It does not need to run an AI model, replace an issue tracker, or
become a monitoring platform. Its stable product boundary is the issue and evidence contract shared
by people, projects, and development agents.

## Documentation

The documentation is organized as a project wiki. Start at the
[Wiki Home](docs/README.md), or go directly to:

- [Product Vision](docs/product/vision.md)
- [Core Workflow and Domain Model](docs/product/workflow.md)
- [Web Application](docs/product/web-application.md)
- [System Architecture](docs/architecture/overview.md)
- [Evidence Pipeline](docs/architecture/evidence-pipeline.md)
- [Issue Bundle v1](docs/contracts/issue-bundle-v1.md)
- [Project Integration](docs/integrations/project-integration.md)
- [Development Agent Interface](docs/integrations/agent-interface.md)
- [Security](docs/security.md)
- [MVP Plan](docs/mvp.md)

## Status

The project is in the design stage. The first implementation will prove one complete flow:

```text
record problem -> build issue bundle -> agent analyzes code -> developer confirms fix -> reuse case
```

Dayboard may be the first reference integration, but DebugRelay must remain project-independent.

## Repository

Implementation has not started. Project-wide instructions for coding agents live in
[AGENTS.md](AGENTS.md).
