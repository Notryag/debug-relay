# Command-Line Interface

[Wiki Home](README.md)

## Role

The `debugrelay` CLI is a thin adapter over the public REST API. It does not connect to PostgreSQL,
run a model, or implement a second set of workflow rules. JSON request bodies remain governed by
the FastAPI OpenAPI document, and exported ZIP files remain governed by Issue Bundle v1.

The CLI supports both interactive developer use and file-oriented development agents. Successful
commands write JSON to stdout, errors go to stderr, and structured input can come from a UTF-8 JSON
file or stdin using `-`.

## Install and Configure

From a source checkout:

```bash
uv sync --dev
uv run debugrelay --help
```

For repeated use, install the checkout as a tool:

```bash
uv tool install .
debugrelay --help
```

Set the API address and one token appropriate for the next command:

```bash
export DEBUGRELAY_URL=http://127.0.0.1:8010
export DEBUGRELAY_TOKEN='<scoped-token>'
```

Do not put bearer tokens in committed files. Environment variables are preferred over `--token`
because command-line arguments may be retained in shell history or visible in process listings. The
CLI never persists a token. It accepts plain HTTP only for loopback hosts; remote servers must use
HTTPS. Redirects are not followed, so credentials are not forwarded to another origin.

## Token Scopes

| Operation | Token |
| --- | --- |
| Create a project | admin |
| Show a project | admin, project intake, or project agent |
| Create an issue or attach evidence | admin or matching project intake |
| List or show issues | admin, matching project intake, or matching project agent |
| Export, find similar issues, or report analysis | admin or matching project agent |
| Confirm resolution | admin |

Project creation returns intake and agent tokens exactly once. Store them in the deployment's
secret manager; DebugRelay stores only their SHA-256 hashes.

## Commands

```text
debugrelay project create PROJECT_JSON
debugrelay project show PROJECT_ID

debugrelay issue create ISSUE_JSON
debugrelay issue list --project PROJECT_ID [--state STATE]
debugrelay issue show ISSUE_ID
debugrelay issue attach ISSUE_ID PATH
debugrelay issue export ISSUE_ID [-o BUNDLE_ZIP]
debugrelay issue similar ISSUE_ID
debugrelay issue report-analysis ISSUE_ID ANALYSIS_JSON
debugrelay issue resolve ISSUE_ID RESOLUTION_JSON
```

Run any command with `--help` for its limits and optional metadata.

## End-to-End Flow

Start the API as described in [Backend Development](development.md), then use the checked examples.
The project command requires the admin token:

```bash
export DEBUGRELAY_TOKEN='<admin-token>'
debugrelay project create examples/cli/project-create.json > project-created.json
```

The response contains one-time project credentials. Set the intake token and create an issue:

```bash
export DEBUGRELAY_TOKEN='<intake-token>'
debugrelay issue create examples/cli/issue-create.json > issue-created.json
```

The issue response contains the generated issue and anchor-evidence IDs. Additional UTF-8 text or
JSON evidence can be attached without exposing the local absolute path in provenance:

```bash
debugrelay issue attach ISSUE_ID error.log \
  --kind log \
  --summary 'Focused checkout failure log' \
  --observed-at 2026-07-14T03:00:00Z
```

Use the project agent token to inspect and export the issue:

```bash
export DEBUGRELAY_TOKEN='<agent-token>'
debugrelay issue show ISSUE_ID
debugrelay issue export ISSUE_ID -o issue-bundle.zip
debugrelay issue similar ISSUE_ID
```

An external development agent reads `issue-bundle.zip` and the authorized source checkout. Replace
`EVIDENCE-ID` in the analysis example with an ID from the issue, then report the result:

```bash
debugrelay issue report-analysis ISSUE_ID examples/cli/analysis-create.json
```

After a developer reviews the analysis and verifies the actual fix, replace `ANALYSIS-ID`,
`EVIDENCE-ID`, and the fixture commit in the resolution example. Resolution confirmation requires
the admin token:

```bash
export DEBUGRELAY_TOKEN='<admin-token>'
debugrelay issue resolve ISSUE_ID examples/cli/resolution-create.json
```

The four request examples are validated against the same Pydantic models used by the API. They are
templates, not evidence that the example root cause or fix was actually confirmed.

## Input and Output Contract

- `-` reads one bounded UTF-8 JSON document from stdin.
- Duplicate JSON object keys, `NaN`, and infinite numeric values are rejected locally.
- Request JSON is sent unchanged; validation and redaction remain server responsibilities.
- Attachment reads are capped at 10 MiB and normalized to UTC observation time.
- The current `attach` command accepts UTF-8 text and JSON. Binary artifact upload is deferred until
  the artifact-storage API exists.
- Bundle downloads default to a 256 MiB client cap, write through a temporary file, and do not
  overwrite an existing destination unless `--force` is supplied.
- A success exits `0`, an API or network failure exits `1`, and invalid local input or configuration
  exits `2`.

The CLI deliberately emits JSON rather than presentation-oriented tables so shell tools and agents
can consume the same output. The API's error code, request ID, and validation details are preserved
on stderr without printing response bodies or bearer tokens.

Related: [Development Agent Interface](integrations/agent-interface.md),
[Issue Bundle v1](contracts/issue-bundle-v1.md), and [Security](security.md).
