# Web Application

[Wiki Home](../README.md)

## Role of the Web UI

The web application is the developer workspace for monitoring error groups, reviewing automatically
opened cases, inspecting agent conclusions, and confirming resolutions. Projects continuously
integrate through event sources and collectors; the UI is not primarily an issue-submission form.

The first screen is the error-group inbox. DebugRelay does not need a marketing page, generic
infrastructure dashboard, or chat-first interface.

## Error-Group Inbox

The inbox is a compact operational list showing:

- normalized error summary, project, environment, component, and service
- total count, recent-window count, first seen, and last seen
- highest severity and affected release or commit
- new, recurring, regressed, awaiting-revision, or case-opened detection status
- active case and agent-analysis state
- similar resolved-case indicator
- project, environment, component, severity, time, and status filters

The default order prioritizes new critical errors, regressions, and recent rate increases. Repeated
events update an existing row instead of producing a noisy list of individual occurrences.

## Error-Group Detail

The group detail explains the monitoring decision:

```text
Error type / normalized message / severity / project / component
Count trend / first seen / last seen / affected releases
[Open active case] [Inspect sample] [Mute policy later]

Representative sanitized event
Occurrence buckets
Source and correlation references
Detection history
Current and previous development cases
```

## Development-Case Detail

The case page is the human and agent-review workspace:

```text
Case ID / error group / state / project / exact revision
[Export bundle] [Copy agent command] [Resolve]

Detection reason and occurrence context
Selected evidence
Agent facts, hypotheses, code locations, and checks
Confirmed root cause, fix revision, tests, and outcome
Post-fix recurrence status
```

Evidence references and source-code locations must be directly navigable. Large raw artifacts open
in a bounded viewer or download and do not expand the main layout without a limit.

## Project Settings

Project settings contain integration and safety configuration:

- repository and allowed workspace mappings
- scoped source, agent, and human credentials
- event sources and collector health
- redaction, event-size, detection, and retention policy
- release-to-commit mappings
- webhook, OpenTelemetry, Docker, CLI, and agent setup instructions

## Manual Fallback

Manual case creation may exist under a secondary action for local or otherwise unobservable
failures. It is never the main screen or the expected path for normal production errors.

## Responsive Behavior

Desktop may show group statistics or evidence navigation beside selected content. Mobile collapses
navigation into tabs or a menu while keeping group identity, counts, case state, and primary actions
visible. Fixed headers and toolbars must not obscure content.

Related: [Product Vision](vision.md), [Core Workflow](workflow.md), and
[MVP Plan](../mvp.md).
