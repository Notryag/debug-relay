from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from debugrelay import cli
from debugrelay.client import ClientSettings, DebugRelayClient


runner = CliRunner()


@pytest.fixture
def mock_api(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if request.method == "GET" and path == "/api/projects/project-1":
            return httpx.Response(200, json={"id": "project-1", "name": "Demo"}, request=request)
        if request.method == "GET" and path == "/api/issues":
            return httpx.Response(200, json={"items": []}, request=request)
        if request.method == "GET" and path == "/api/issues/ISSUE-1":
            return httpx.Response(200, json={"id": "ISSUE-1", "state": "open"}, request=request)
        if request.method == "GET" and path == "/api/issues/ISSUE-1/similar":
            return httpx.Response(200, json={"items": []}, request=request)
        if request.method == "GET" and path == "/api/error-groups":
            return httpx.Response(200, json={"items": []}, request=request)
        if request.method == "GET" and path == "/api/error-groups/GROUP-1":
            return httpx.Response(200, json={"id": "GROUP-1"}, request=request)
        if request.method == "GET" and path == "/api/issues/ISSUE-1/bundle":
            return httpx.Response(200, content=b"zip-content", request=request)
        if request.method == "POST" and path == "/api/projects":
            return httpx.Response(201, json={"id": "project-1"}, request=request)
        if request.method == "POST" and path == "/api/issues":
            return httpx.Response(201, json={"id": "ISSUE-1"}, request=request)
        if request.method == "POST" and path == "/api/issues/ISSUE-1/evidence":
            return httpx.Response(201, json={"id": "EVIDENCE-1"}, request=request)
        if request.method == "POST" and path == "/api/issues/ISSUE-1/analyses":
            return httpx.Response(201, json={"id": "ANALYSIS-1"}, request=request)
        if request.method == "POST" and path == "/api/issues/ISSUE-1/resolve":
            return httpx.Response(
                200, json={"issue_id": "ISSUE-1", "human_confirmed": True}, request=request
            )
        return httpx.Response(
            404, json={"error": {"code": "NOT_FOUND", "message": "not found"}}, request=request
        )

    transport = httpx.MockTransport(handler)

    def fake_open(options: cli.CliOptions) -> DebugRelayClient:
        return DebugRelayClient(
            ClientSettings(
                base_url=options.url,
                token=options.token or "test-token",
                timeout=options.timeout,
            ),
            transport=transport,
        )

    monkeypatch.setattr(cli, "open_client", fake_open)
    return requests


def invoke(*args: str, input: str | None = None):
    return runner.invoke(
        cli.app,
        ["--url", "https://debugrelay.example", "--token", "test-token", *args],
        input=input,
    )


def request_json(request: httpx.Request) -> dict[str, Any]:
    return json.loads(request.content.decode("utf-8"))


def test_project_and_issue_create_accept_stdin(mock_api: list[httpx.Request]) -> None:
    project_result = invoke("project", "create", "-", input='{"id":"project-1","name":"Demo"}')
    assert project_result.exit_code == 0, project_result.output
    assert json.loads(project_result.stdout)["id"] == "project-1"
    assert request_json(mock_api[-1]) == {"id": "project-1", "name": "Demo"}

    issue_result = invoke("issue", "create", "-", input='{"project_id":"project-1"}')
    assert issue_result.exit_code == 0, issue_result.output
    assert mock_api[-1].url.path == "/api/issues"


@pytest.mark.parametrize(
    ("args", "path"),
    [
        (("project", "show", "project-1"), "/api/projects/project-1"),
        (("issue", "show", "ISSUE-1"), "/api/issues/ISSUE-1"),
        (("issue", "list", "--project", "project-1"), "/api/issues"),
        (("issue", "similar", "ISSUE-1"), "/api/issues/ISSUE-1/similar"),
        (("groups", "list", "--project", "project-1"), "/api/error-groups"),
        (("groups", "show", "GROUP-1"), "/api/error-groups/GROUP-1"),
    ],
)
def test_read_commands_map_to_rest_resources(
    mock_api: list[httpx.Request],
    args: tuple[str, ...],
    path: str,
) -> None:
    result = invoke(*args)
    assert result.exit_code == 0, result.output
    assert mock_api[-1].url.path == path
    assert mock_api[-1].headers["authorization"] == "Bearer test-token"


def test_attach_uses_path_free_provenance_and_normalizes_time(
    tmp_path: Path,
    mock_api: list[httpx.Request],
) -> None:
    attachment = tmp_path / "failure.log"
    attachment.write_text("Authorization: Bearer should-be-redacted\n", encoding="utf-8")
    result = invoke(
        "issue",
        "attach",
        "ISSUE-1",
        str(attachment),
        "--observed-at",
        "2026-07-14T12:00:00+08:00",
    )
    assert result.exit_code == 0, result.output
    payload = request_json(mock_api[-1])
    assert payload["source"]["locator"] == "cli://attachment/failure.log"
    assert str(tmp_path) not in json.dumps(payload)
    assert payload["observed_at"] == "2026-07-14T04:00:00Z"
    assert payload["content"] == "Authorization: Bearer should-be-redacted\n"
    assert payload["attributes"]["filename"] == "failure.log"


def test_export_writes_bundle_and_report_and_resolve_read_json(
    tmp_path: Path,
    mock_api: list[httpx.Request],
) -> None:
    destination = tmp_path / "issue.zip"
    export_result = invoke("issue", "export", "ISSUE-1", "--output", str(destination))
    assert export_result.exit_code == 0, export_result.output
    assert destination.read_bytes() == b"zip-content"
    assert json.loads(export_result.stdout)["size_bytes"] == len(b"zip-content")

    analysis = tmp_path / "analysis.json"
    analysis.write_text('{"agent":{"name":"agent"}}', encoding="utf-8")
    analysis_result = invoke("issue", "report-analysis", "ISSUE-1", str(analysis))
    assert analysis_result.exit_code == 0, analysis_result.output
    assert mock_api[-1].url.path == "/api/issues/ISSUE-1/analyses"
    assert request_json(mock_api[-1]) == {"agent": {"name": "agent"}}

    resolution = tmp_path / "resolution.json"
    resolution.write_text('{"analysis_id":"ANALYSIS-1"}', encoding="utf-8")
    resolve_result = invoke("issue", "resolve", "ISSUE-1", str(resolution))
    assert resolve_result.exit_code == 0, resolve_result.output
    assert mock_api[-1].url.path == "/api/issues/ISSUE-1/resolve"


def test_local_input_and_api_errors_have_stable_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    local_result = runner.invoke(
        cli.app,
        ["--url", "http://remote.example", "--token", "test-token", "issue", "show", "ISSUE-1"],
    )
    assert local_result.exit_code == 2
    assert "HTTPS" in local_result.output

    def error_open(options: cli.CliOptions) -> DebugRelayClient:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                422,
                json={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "bad input",
                        "request_id": "req-cli",
                        "details": {"field": "summary"},
                    }
                },
                request=request,
            )

        return DebugRelayClient(
            ClientSettings(options.url, options.token or "test-token"),
            transport=httpx.MockTransport(handler),
        )

    monkeypatch.setattr(cli, "open_client", error_open)
    api_result = invoke("issue", "show", "ISSUE-1")
    assert api_result.exit_code == 1
    assert "VALIDATION_ERROR" in api_result.output
    assert "req-cli" in api_result.output
    assert "summary" in api_result.output


def test_duplicate_json_keys_and_binary_attachments_are_rejected(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"id":"one","id":"two"}', encoding="utf-8")
    duplicate_result = invoke("project", "create", str(duplicate))
    assert duplicate_result.exit_code == 2
    assert "duplicate JSON key" in duplicate_result.output

    binary = tmp_path / "capture.bin"
    binary.write_bytes(b"\x00\x01\x02")
    binary_result = invoke("issue", "attach", "ISSUE-1", str(binary))
    assert binary_result.exit_code == 2
    assert "binary attachment" in binary_result.output
