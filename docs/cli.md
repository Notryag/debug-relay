# Command-Line Interface

[Wiki Home](README.md)

## Role

The `debugrelay` CLI is an operational and development-agent adapter over the public REST API. It
does not connect to PostgreSQL, run a model, or implement separate workflow rules.

In the monitoring-first product, developers use the CLI to inspect error groups, inspect and export
automatically opened cases, report agent analysis, and confirm reviewed resolutions. Existing raw
JSON project and case creation commands remain low-level bootstrap and adapter-debugging interfaces;
they are not the normal developer workflow and have no user-facing form templates.

## Install and Configure

```bash
uv sync --dev
uv run debugrelay --help
```

For repeated use:

```bash
uv tool install .
debugrelay --help
```

Set the API address and a token appropriate for the command:

```bash
export DEBUGRELAY_URL=http://127.0.0.1:8010
export DEBUGRELAY_TOKEN='<scoped-token>'
```

Do not put bearer tokens in committed files. Environment variables are preferred over `--token`
because command-line arguments may remain in shell history or process listings. The CLI never
persists a token, accepts plain HTTP only for loopback hosts, and does not follow redirects.

## Monitoring Commands

The monitoring slice currently exposes error-group inspection:

```text
debugrelay groups list --project PROJECT_ID
debugrelay groups show GROUP_ID
```

These commands require a project agent or admin token. Intake tokens are deliberately write-only for
monitoring resources.

The following case-oriented aliases are the next CLI step; the existing `issue` commands already
provide the same REST operations:

```text
debugrelay case show CASE_ID
debugrelay case export CASE_ID [-o BUNDLE_ZIP]
debugrelay case similar CASE_ID
debugrelay case report-analysis CASE_ID ANALYSIS_JSON
debugrelay case resolve CASE_ID RESOLUTION_JSON
```

The existing `issue` command name remains the implemented API surface while Issue Bundle v1 uses the
term `issue`. The product-facing term is `DevelopmentCase`.

## Current Low-Level Commands

```text
debugrelay project create PROJECT_JSON
debugrelay project show PROJECT_ID
debugrelay issue create ISSUE_JSON
debugrelay issue list --project PROJECT_ID
debugrelay issue show ISSUE_ID
debugrelay issue attach ISSUE_ID PATH
debugrelay issue export ISSUE_ID
debugrelay issue similar ISSUE_ID
debugrelay issue report-analysis ISSUE_ID ANALYSIS_JSON
debugrelay issue resolve ISSUE_ID RESOLUTION_JSON
```

Raw JSON input is retained for source-adapter development, API debugging, and external agents that
already produce the canonical structured result. It is not documentation for an end user to fill in.

Successful commands write JSON to stdout and errors to stderr. Local input or configuration errors
exit `2`; API or network failures exit `1`; success exits `0`. Bundle downloads are bounded, use a
temporary file, and do not overwrite an existing destination without `--force`.

Related: [Product Vision](product/vision.md),
[Development Agent Interface](integrations/agent-interface.md), and [Security](security.md).
