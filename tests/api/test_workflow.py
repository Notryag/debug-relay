from __future__ import annotations

from io import BytesIO
from hashlib import sha256
import json
from zipfile import ZipFile

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from debugrelay.config import Settings
from debugrelay.models import ProjectRow
from debugrelay.services.bundle import BUNDLE_VALIDATOR


ADMIN_TOKEN = "test-admin-token-with-at-least-32-characters"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def project_payload(project_id: str = "example-api") -> dict:
    return {
        "id": project_id,
        "name": "Example API",
        "redaction_policy_version": "default-v1",
        "repositories": [
            {
                "id": "repo-main",
                "locator": f"https://example.invalid/{project_id}.git",
            }
        ],
    }


def issue_payload(
    *, project_id: str = "example-api", fingerprint: str = "checkout-timeout-v1"
) -> dict:
    return {
        "project_id": project_id,
        "environment": "production",
        "component": "checkout-api",
        "occurred_at": "2026-07-14T03:00:00Z",
        "summary": "Checkout fails while waiting for inventory",
        "expected": "Checkout creates an order.",
        "actual": "Checkout fails with token=issue-secret-value.",
        "reproduction": ["Submit checkout for an in-stock item."],
        "fingerprint": fingerprint,
        "repositories": [
            {
                "repository_id": "repo-main",
                "role": "primary",
                "commit_sha": "1" * 40,
                "branch": "main",
            }
        ],
        "evidence": {
            "kind": "exception",
            "summary": "Inventory timeout with Authorization: Bearer summary-secret",
            "observed_at": "2026-07-14T03:00:00Z",
            "source": {
                "adapter": "structured-log",
                "locator": "logs://example-api/checkout-api",
                "selector": "request_id=request-123 token=selector-secret",
            },
            "relation": "anchor",
            "content_type": "application/json",
            "content": {
                "exception": {
                    "type": "InventoryTimeout",
                    "message": "Inventory request timed out.",
                },
                "authorization": "Bearer content-secret",
                "password": "database-secret",
                "request_id": "request-123",
            },
            "attributes": {
                "request_id": "request-123",
                "api_key": "attribute-secret",
            },
        },
    }


def analysis_payload(evidence_id: str) -> dict:
    citation = {"kind": "evidence", "evidence_id": evidence_id}
    source_citation = {
        "kind": "source",
        "location": {
            "repository_id": "repo-main",
            "path": "src/inventory/client.py",
            "symbol": "InventoryClient.reserve",
            "line_start": 40,
            "line_end": 55,
        },
    }
    check = {
        "id": "CHECK-1",
        "description": "Run the focused timeout test.",
        "command": "pytest tests/test_inventory.py -q",
        "status": "passed",
        "result": "1 passed",
        "evidence_refs": [evidence_id],
    }
    return {
        "agent": {"name": "example-coding-agent", "version": "1.0"},
        "status": "complete",
        "facts": [
            {
                "id": "FACT-1",
                "statement": "The inventory request exceeded its configured timeout.",
                "citations": [citation],
            }
        ],
        "hypotheses": [
            {
                "id": "HYPOTHESIS-1",
                "rank": 1,
                "statement": "The inventory timeout is too short for the checkout path.",
                "status": "supported",
                "citations": [citation, source_citation],
                "verification_steps": [check],
            }
        ],
        "missing_information": [],
        "proposed_changes": [
            {
                "location": source_citation["location"],
                "summary": "Use the checkout-specific inventory timeout.",
            }
        ],
        "checks": [check],
    }


async def create_project(client: AsyncClient, project_id: str = "example-api") -> dict:
    response = await client.post(
        "/api/projects",
        headers=auth(ADMIN_TOKEN),
        json=project_payload(project_id),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_complete_issue_to_resolution_workflow(
    client: AsyncClient,
    settings: Settings,
) -> None:
    project = await create_project(client)
    intake_token = project["credentials"]["intake_token"]
    agent_token = project["credentials"]["agent_token"]

    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        project_row = await session.scalar(select(ProjectRow).where(ProjectRow.id == "example-api"))
        assert project_row is not None
        assert project_row.intake_token_hash != intake_token
        assert project_row.agent_token_hash != agent_token
        assert len(project_row.intake_token_hash) == 64
        assert len(project_row.agent_token_hash) == 64
    await engine.dispose()

    issue_response = await client.post(
        "/api/issues",
        headers=auth(intake_token),
        json=issue_payload(),
    )
    assert issue_response.status_code == 201, issue_response.text
    issue = issue_response.json()
    issue_id = issue["id"]
    evidence_id = issue["evidence"][0]["id"]
    assert issue["state"] == "open"
    assert "issue-secret-value" not in issue["actual"]
    assert issue["evidence"][0]["redaction_count"] >= 5

    denied_content = await client.get(
        f"/api/issues/{issue_id}/evidence/{evidence_id}/content",
        headers=auth(intake_token),
    )
    assert denied_content.status_code == 403

    content_response = await client.get(
        f"/api/issues/{issue_id}/evidence/{evidence_id}/content",
        headers=auth(agent_token),
    )
    assert content_response.status_code == 200
    assert "content-secret" not in content_response.text
    assert "database-secret" not in content_response.text
    assert content_response.text.count("[REDACTED]") >= 2

    analysis_response = await client.post(
        f"/api/issues/{issue_id}/analyses",
        headers=auth(agent_token),
        json=analysis_payload(evidence_id),
    )
    assert analysis_response.status_code == 201, analysis_response.text
    analysis = analysis_response.json()

    issue_after_analysis = await client.get(
        f"/api/issues/{issue_id}",
        headers=auth(agent_token),
    )
    assert issue_after_analysis.json()["state"] == "analyzing"

    resolution_payload = {
        "confirmed_by_id": "developer-1",
        "confirmed_by_display_name": "Example Developer",
        "analysis_id": analysis["id"],
        "root_cause": "Checkout used a timeout that was too short for inventory reservations.",
        "conditions": ["Inventory response takes longer than the shared timeout."],
        "fixes": [
            {
                "repository_id": "repo-main",
                "commit_sha": "2" * 40,
                "changed_files": [
                    {
                        "path": "src/inventory/client.py",
                        "summary": "Use the checkout-specific timeout.",
                    }
                ],
            }
        ],
        "verification": [
            {
                "id": "VERIFY-1",
                "description": "Run the focused inventory timeout test.",
                "command": "pytest tests/test_inventory.py -q",
                "status": "passed",
                "result": "1 passed",
                "verified_at": "2026-07-14T03:20:00Z",
                "evidence_refs": [evidence_id],
            }
        ],
        "observed_in_environment": True,
    }

    denied_resolution = await client.post(
        f"/api/issues/{issue_id}/resolve",
        headers=auth(agent_token),
        json=resolution_payload,
    )
    assert denied_resolution.status_code == 403

    resolution_response = await client.post(
        f"/api/issues/{issue_id}/resolve",
        headers=auth(ADMIN_TOKEN),
        json=resolution_payload,
    )
    assert resolution_response.status_code == 200, resolution_response.text
    assert resolution_response.json()["human_confirmed"] is True

    bundle_response = await client.get(
        f"/api/issues/{issue_id}/bundle",
        headers=auth(agent_token),
    )
    assert bundle_response.status_code == 200, bundle_response.text
    assert bundle_response.headers["content-type"] == "application/zip"
    assert b"content-secret" not in bundle_response.content
    assert b"database-secret" not in bundle_response.content
    with ZipFile(BytesIO(bundle_response.content)) as archive:
        assert {"bundle.json", "summary.md"} <= set(archive.namelist())
        bundle = json.loads(archive.read("bundle.json"))
        assert not list(BUNDLE_VALIDATOR.iter_errors(bundle))
        assert bundle["issue"]["state"] == "resolved"
        assert bundle["resolution"]["analysis_id"] == analysis["id"]
        evidence_content = archive.read(bundle["evidence"][0]["content_ref"])
        assert b"[REDACTED]" in evidence_content
        assert len(evidence_content) == bundle["evidence"][0]["size_bytes"]
        assert bundle["evidence"][0]["content_hash"] == (
            f"sha256:{sha256(evidence_content).hexdigest()}"
        )

    second_issue_response = await client.post(
        "/api/issues",
        headers=auth(intake_token),
        json=issue_payload(),
    )
    assert second_issue_response.status_code == 201
    second_issue_id = second_issue_response.json()["id"]
    similar_response = await client.get(
        f"/api/issues/{second_issue_id}/similar",
        headers=auth(agent_token),
    )
    assert similar_response.status_code == 200, similar_response.text
    assert similar_response.json()["items"][0]["issue_id"] == issue_id
    assert similar_response.json()["items"][0]["similarity"] == 1.0


async def test_project_scope_and_analysis_references_are_enforced(client: AsyncClient) -> None:
    first = await create_project(client, "project-one")
    second = await create_project(client, "project-two")

    issue_response = await client.post(
        "/api/issues",
        headers=auth(first["credentials"]["intake_token"]),
        json=issue_payload(project_id="project-one"),
    )
    assert issue_response.status_code == 201
    issue = issue_response.json()

    cross_project = await client.get(
        f"/api/issues/{issue['id']}",
        headers=auth(second["credentials"]["agent_token"]),
    )
    assert cross_project.status_code == 403

    invalid_analysis = analysis_payload(issue["evidence"][0]["id"])
    invalid_analysis["facts"][0]["citations"][0]["evidence_id"] = "EVIDENCE-MISSING"
    analysis_response = await client.post(
        f"/api/issues/{issue['id']}/analyses",
        headers=auth(first["credentials"]["agent_token"]),
        json=invalid_analysis,
    )
    assert analysis_response.status_code == 422
    assert analysis_response.json()["error"]["code"] == "ANALYSIS_EVIDENCE_INVALID"


async def test_repository_locator_cannot_contain_credentials(client: AsyncClient) -> None:
    payload = project_payload()
    payload["repositories"][0]["locator"] = "https://user:secret@example.invalid/project.git"
    response = await client.post(
        "/api/projects",
        headers=auth(ADMIN_TOKEN),
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REPOSITORY_LOCATOR_CREDENTIALS"


async def test_authentication_is_required(client: AsyncClient) -> None:
    response = await client.post("/api/projects", json=project_payload())
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"
