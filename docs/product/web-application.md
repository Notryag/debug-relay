# Web Application

[Wiki Home](../README.md)

## Role of the Web UI

The web application supports the human parts of the workflow: reporting, reviewing evidence,
checking agent conclusions, and confirming resolutions. Projects and agents primarily integrate
through the API, CLI, or MCP adapter.

The first screen is the issue inbox. DebugRelay does not need a marketing page, monitoring
dashboard, or chat-first interface.

## Issue Inbox

The inbox is a compact, work-focused list showing:

- issue summary, project, and component
- occurrence time and source revision
- `open`, `analyzing`, or `resolved` state
- evidence completeness
- agent-analysis status
- similar resolved-case indicator
- text, fingerprint, project, and state filters

Creating an issue should be available from the inbox without introducing a separate setup flow.

## Issue Detail

The detail page is the primary workspace:

```text
Issue ID / summary / state / project / revision
[Export bundle] [Copy agent command] [Resolve]

Problem
  Expected | Actual | Reproduction

Evidence
  Stack | Logs | Requests | Changes | Runtime | Attachments

Agent analysis
  Facts | Hypotheses | Code locations | Verification steps

Resolution
  Confirmed root cause | Fix revision | Tests | Outcome
```

The page should prioritize scanability over decorative cards. Evidence references and source-code
locations must be directly navigable. Large raw artifacts open in a dedicated viewer or download;
they do not expand the main layout without a limit.

## Project Settings

Project settings contain only integration and safety configuration:

- repository and allowed workspace mappings
- scoped intake tokens
- evidence-source adapters
- redaction, size, and retention policy
- CLI, webhook, and agent setup instructions

## Knowledge Retrieval

Resolved issues stay in the same searchable issue collection for the MVP. A separate knowledge-base
page is unnecessary until the resolved-case library develops a distinct workflow.

## Responsive Behavior

Desktop may show evidence navigation beside the selected content. Mobile should collapse that
navigation into tabs or a menu while keeping issue identity and primary actions visible. Fixed
headers and toolbars must not obscure evidence or resolution content.

Related: [Product Vision](vision.md), [Agent Interface](../integrations/agent-interface.md), and
[MVP Plan](../mvp.md).
