from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import mimetypes
from pathlib import Path
import re
import sys
from typing import Annotated, Any, Iterator
from urllib.parse import quote

import typer

from debugrelay import __version__
from debugrelay.client import (
    DEFAULT_DOWNLOAD_LIMIT,
    DEFAULT_TIMEOUT_SECONDS,
    ClientConfigurationError,
    ClientSettings,
    DebugRelayClient,
    DebugRelayClientError,
)


DEFAULT_SERVER_URL = "http://127.0.0.1:8010"
MAX_INPUT_BYTES = 16 * 1024 * 1024
DEFAULT_EVIDENCE_BYTES = 10 * 1024 * 1024
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")


class CliInputError(ValueError):
    pass


@dataclass(frozen=True)
class CliOptions:
    url: str
    token: str | None
    timeout: float


app = typer.Typer(
    name="debugrelay",
    help="Continuous error monitoring and AI development-case CLI.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)
project_app = typer.Typer(help="Register and inspect DebugRelay projects.", no_args_is_help=True)
issue_app = typer.Typer(
    help="Inspect and resolve development cases; manual creation is a fallback.",
    no_args_is_help=True,
)
groups_app = typer.Typer(help="Inspect continuously observed error groups.", no_args_is_help=True)
app.add_typer(project_app, name="project")
app.add_typer(issue_app, name="issue")
app.add_typer(groups_app, name="groups")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"debugrelay {__version__}")
        raise typer.Exit()


@app.callback()
def configure(
    ctx: typer.Context,
    url: Annotated[
        str,
        typer.Option(
            "--url",
            envvar="DEBUGRELAY_URL",
            help="DebugRelay server URL (HTTP is allowed only for loopback hosts).",
        ),
    ] = DEFAULT_SERVER_URL,
    token: Annotated[
        str | None,
        typer.Option(
            "--token",
            envvar="DEBUGRELAY_TOKEN",
            help="Bearer token; prefer DEBUGRELAY_TOKEN to avoid shell history.",
            hide_input=True,
        ),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="HTTP timeout in seconds."),
    ] = DEFAULT_TIMEOUT_SECONDS,
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True),
    ] = False,
) -> None:
    del version
    ctx.ensure_object(dict)
    ctx.obj["options"] = CliOptions(url=url, token=token, timeout=timeout)


def _options(ctx: typer.Context) -> CliOptions:
    root = ctx.find_root()
    options = (root.obj or {}).get("options")
    if not isinstance(options, CliOptions):
        raise CliInputError("CLI options were not initialized")
    return options


def open_client(options: CliOptions) -> DebugRelayClient:
    if options.token is None:
        raise ClientConfigurationError(
            "a bearer token is required; set DEBUGRELAY_TOKEN or pass --token"
        )
    return DebugRelayClient(
        ClientSettings(
            base_url=options.url,
            token=options.token,
            timeout=options.timeout,
        )
    )


def _fail_local(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=2)


def _fail_client(error: DebugRelayClientError | ClientConfigurationError) -> None:
    if isinstance(error, ClientConfigurationError):
        _fail_local(str(error))
    suffix: list[str] = []
    if error.status_code is not None:
        suffix.append(f"HTTP {error.status_code}")
    if error.request_id:
        suffix.append(f"request {error.request_id}")
    suffix_text = f" ({', '.join(suffix)})" if suffix else ""
    typer.echo(f"Error: {error.code}: {error.message}{suffix_text}", err=True)
    if error.details is not None:
        typer.echo(
            json.dumps(error.details, ensure_ascii=False, indent=2, sort_keys=True),
            err=True,
        )
    raise typer.Exit(code=1)


@contextmanager
def connected(ctx: typer.Context) -> Iterator[DebugRelayClient]:
    try:
        with open_client(_options(ctx)) as client:
            yield client
    except (ClientConfigurationError, DebugRelayClientError) as error:
        _fail_client(error)


def _emit_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _reject_constant(value: str) -> None:
    raise CliInputError(f"JSON constant is not allowed: {value}")


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CliInputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_source_bytes(source: str, *, max_bytes: int = MAX_INPUT_BYTES) -> bytes:
    if max_bytes < 1:
        raise CliInputError("input size limit must be greater than zero")
    if source == "-":
        stream = getattr(sys.stdin, "buffer", sys.stdin)
        value = stream.read(max_bytes + 1)
        raw = value.encode("utf-8") if isinstance(value, str) else value
    else:
        path = Path(source)
        if not path.exists():
            raise CliInputError(f"input file does not exist: {path}")
        if not path.is_file():
            raise CliInputError(f"input path is not a file: {path}")
        try:
            if path.stat().st_size > max_bytes:
                raise CliInputError(f"input exceeds the {max_bytes} byte limit")
            raw = path.read_bytes()
        except OSError as exc:
            raise CliInputError(f"could not read input file: {path}") from exc
    if len(raw) > max_bytes:
        raise CliInputError(f"input exceeds the {max_bytes} byte limit")
    return raw


def _decode_utf8(raw: bytes, source: str) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CliInputError(f"input is not valid UTF-8: {source}") from exc


def _read_json(source: str, *, require_object: bool = True) -> Any:
    raw = _read_source_bytes(source)
    text = _decode_utf8(raw, source)
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_pairs,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, CliInputError, ValueError) as exc:
        if isinstance(exc, CliInputError):
            raise
        raise CliInputError(f"invalid JSON input: {source}: {exc}") from exc
    if require_object and not isinstance(value, dict):
        raise CliInputError(f"JSON input must be an object: {source}")
    return value


def _normalize_timestamp(value: str | None) -> str:
    if value is None:
        current = datetime.now(timezone.utc)
        return current.isoformat().replace("+00:00", "Z")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CliInputError(f"invalid timestamp: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CliInputError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_identifier(value: str, label: str = "ID") -> None:
    if not IDENTIFIER.fullmatch(value):
        raise CliInputError(f"{label} must match {IDENTIFIER.pattern}")


def _project_path(project_id: str) -> str:
    _safe_identifier(project_id, "project ID")
    return f"api/projects/{quote(project_id, safe='')}"


def _attachment_content(path: Path, content_type: str | None, max_bytes: int) -> tuple[Any, str]:
    raw = _read_source_bytes(str(path), max_bytes=max_bytes)
    guessed_type = mimetypes.guess_type(path.name)[0]
    selected_type = (content_type or guessed_type or "text/plain").split(";", 1)[0].strip()
    if selected_type == "application/json" or selected_type.endswith("+json"):
        text = _decode_utf8(raw, str(path))
        try:
            value = json.loads(
                text,
                object_pairs_hook=_object_pairs,
                parse_constant=_reject_constant,
            )
        except (json.JSONDecodeError, CliInputError, ValueError) as exc:
            if isinstance(exc, CliInputError):
                raise
            raise CliInputError(f"invalid JSON attachment: {path}: {exc}") from exc
        return value, selected_type
    if selected_type.startswith("text/") or selected_type in {
        "application/graphql",
        "application/javascript",
        "application/sql",
        "application/xml",
        "application/x-sh",
        "application/x-yaml",
        "application/yaml",
    }:
        return _decode_utf8(raw, str(path)), selected_type
    raise CliInputError(
        f"binary attachment type {selected_type!r} is not supported by this API; "
        "attach UTF-8 text or JSON for now"
    )


@project_app.command("create")
def project_create(
    ctx: typer.Context,
    input_file: Annotated[str, typer.Argument(help="Project JSON file, or - for stdin.")],
) -> None:
    try:
        payload = _read_json(input_file)
    except CliInputError as error:
        _fail_local(str(error))
    with connected(ctx) as client:
        _emit_json(client.post_json("api/projects", payload))


@project_app.command("show")
def project_show(
    ctx: typer.Context,
    project_id: Annotated[str, typer.Argument(help="Project ID.")],
) -> None:
    try:
        path = _project_path(project_id)
    except CliInputError as error:
        _fail_local(str(error))
    with connected(ctx) as client:
        _emit_json(client.get_json(path))


@issue_app.command("create")
def issue_create(
    ctx: typer.Context,
    input_file: Annotated[str, typer.Argument(help="Issue JSON file, or - for stdin.")],
) -> None:
    try:
        payload = _read_json(input_file)
    except CliInputError as error:
        _fail_local(str(error))
    with connected(ctx) as client:
        _emit_json(client.post_json("api/issues", payload))


@issue_app.command("list")
def issue_list(
    ctx: typer.Context,
    project_id: Annotated[str, typer.Option("--project", help="Project ID.")],
    state: Annotated[str | None, typer.Option("--state", help="Filter by issue state.")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum number of issues.")] = 50,
) -> None:
    try:
        _safe_identifier(project_id, "project ID")
        if limit < 1 or limit > 100:
            raise CliInputError("limit must be between 1 and 100")
    except CliInputError as error:
        _fail_local(str(error))
    params: dict[str, Any] = {"project_id": project_id, "limit": limit}
    if state is not None:
        params["state"] = state
    with connected(ctx) as client:
        _emit_json(client.get_json("api/issues", params=params))


@issue_app.command("show")
def issue_show(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID.")],
) -> None:
    try:
        path = client_issue_path(issue_id)
    except CliInputError as error:
        _fail_local(str(error))
    with connected(ctx) as client:
        _emit_json(client.get_json(path))


def client_issue_path(issue_id: str, suffix: str = "") -> str:
    _safe_identifier(issue_id, "issue ID")
    return f"api/issues/{quote(issue_id, safe='')}{suffix}"


def client_group_path(group_id: str) -> str:
    _safe_identifier(group_id, "error group ID")
    return f"api/error-groups/{quote(group_id, safe='')}"


@groups_app.command("list")
def groups_list(
    ctx: typer.Context,
    project_id: Annotated[str, typer.Option("--project", help="Project ID.")],
    environment: Annotated[
        str | None,
        typer.Option("--environment", help="Filter by environment."),
    ] = None,
    component: Annotated[
        str | None,
        typer.Option("--component", help="Filter by component."),
    ] = None,
    severity: Annotated[
        str | None,
        typer.Option("--severity", help="Filter by warning, error, or critical."),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum number of groups.")] = 50,
) -> None:
    try:
        _safe_identifier(project_id, "project ID")
        if limit < 1 or limit > 100:
            raise CliInputError("limit must be between 1 and 100")
    except CliInputError as error:
        _fail_local(str(error))
    params: dict[str, Any] = {"project_id": project_id, "limit": limit}
    if environment is not None:
        params["environment"] = environment
    if component is not None:
        params["component"] = component
    if severity is not None:
        params["severity"] = severity
    with connected(ctx) as client:
        _emit_json(client.get_json("api/error-groups", params=params))


@groups_app.command("show")
def groups_show(
    ctx: typer.Context,
    group_id: Annotated[str, typer.Argument(help="Error group ID.")],
) -> None:
    try:
        path = client_group_path(group_id)
    except CliInputError as error:
        _fail_local(str(error))
    with connected(ctx) as client:
        _emit_json(client.get_json(path))


@issue_app.command("attach")
def issue_attach(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID.")],
    attachment: Annotated[Path, typer.Argument(help="UTF-8 text or JSON file to attach.")],
    kind: Annotated[str, typer.Option("--kind", help="Evidence kind.")] = "other",
    summary: Annotated[str | None, typer.Option("--summary", help="Evidence summary.")] = None,
    relation: Annotated[str, typer.Option("--relation", help="Evidence relation.")] = "correlated",
    observed_at: Annotated[
        str | None,
        typer.Option("--observed-at", help="Observation timestamp; defaults to now UTC."),
    ] = None,
    content_type: Annotated[
        str | None,
        typer.Option("--content-type", help="Override the MIME type inferred from the filename."),
    ] = None,
    adapter: Annotated[
        str, typer.Option("--adapter", help="Evidence source adapter.")
    ] = "cli-file",
    source_locator: Annotated[
        str | None,
        typer.Option("--source-locator", help="Source locator; defaults to a path-free CLI URI."),
    ] = None,
    selector: Annotated[
        str | None, typer.Option("--selector", help="Optional source selector.")
    ] = None,
    max_bytes: Annotated[
        int,
        typer.Option("--max-bytes", help="Maximum bytes read from the attachment."),
    ] = DEFAULT_EVIDENCE_BYTES,
) -> None:
    try:
        path = client_issue_path(issue_id, "/evidence")
        if not attachment.exists() or not attachment.is_file():
            raise CliInputError(f"attachment is not a file: {attachment}")
        if max_bytes < 1 or max_bytes > DEFAULT_EVIDENCE_BYTES:
            raise CliInputError(f"max-bytes must be between 1 and {DEFAULT_EVIDENCE_BYTES}")
        content, resolved_content_type = _attachment_content(
            attachment,
            content_type,
            max_bytes,
        )
        payload = {
            "kind": kind,
            "summary": summary or f"CLI attachment: {attachment.name}",
            "observed_at": _normalize_timestamp(observed_at),
            "source": {
                "adapter": adapter,
                "locator": source_locator or f"cli://attachment/{quote(attachment.name, safe='')}",
                "selector": selector,
            },
            "relation": relation,
            "content_type": resolved_content_type,
            "content": content,
            "attributes": {
                "filename": attachment.name,
                "original_size_bytes": attachment.stat().st_size,
            },
        }
    except (CliInputError, OSError) as error:
        _fail_local(str(error))
    with connected(ctx) as client:
        _emit_json(client.post_json(path, payload))


@issue_app.command("export")
def issue_export(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="ZIP destination; defaults to ISSUE_ID.zip."),
    ] = None,
    force: Annotated[
        bool, typer.Option("--force", help="Replace an existing output file.")
    ] = False,
    max_bytes: Annotated[
        int,
        typer.Option("--max-bytes", help="Maximum bundle bytes to download."),
    ] = DEFAULT_DOWNLOAD_LIMIT,
) -> None:
    try:
        _safe_identifier(issue_id, "issue ID")
        destination = output or Path(f"{issue_id}.zip")
        if max_bytes < 1:
            raise CliInputError("max-bytes must be greater than zero")
    except CliInputError as error:
        _fail_local(str(error))
    with connected(ctx) as client:
        try:
            size = client.download_bundle(
                issue_id,
                destination,
                overwrite=force,
                max_bytes=max_bytes,
            )
        except DebugRelayClientError as error:
            _fail_client(error)
    _emit_json({"path": str(destination), "size_bytes": size})


@issue_app.command("similar")
def issue_similar(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID.")],
    limit: Annotated[int, typer.Option("--limit", help="Maximum similar issues.")] = 10,
) -> None:
    try:
        path = client_issue_path(issue_id, "/similar")
        if limit < 1 or limit > 20:
            raise CliInputError("limit must be between 1 and 20")
    except CliInputError as error:
        _fail_local(str(error))
    with connected(ctx) as client:
        _emit_json(client.get_json(path, params={"limit": limit}))


@issue_app.command("report-analysis")
def issue_report_analysis(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID.")],
    analysis_json: Annotated[str, typer.Argument(help="Analysis JSON file, or - for stdin.")],
) -> None:
    try:
        path = client_issue_path(issue_id, "/analyses")
        payload = _read_json(analysis_json)
    except CliInputError as error:
        _fail_local(str(error))
    with connected(ctx) as client:
        _emit_json(client.post_json(path, payload))


@issue_app.command("resolve")
def issue_resolve(
    ctx: typer.Context,
    issue_id: Annotated[str, typer.Argument(help="Issue ID.")],
    resolution_json: Annotated[str, typer.Argument(help="Resolution JSON file, or - for stdin.")],
) -> None:
    try:
        path = client_issue_path(issue_id, "/resolve")
        payload = _read_json(resolution_json)
    except CliInputError as error:
        _fail_local(str(error))
    with connected(ctx) as client:
        _emit_json(client.post_json(path, payload))


if __name__ == "__main__":
    app()
