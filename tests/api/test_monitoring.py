from __future__ import annotations

import asyncio
from io import BytesIO
import json
from zipfile import ZipFile

from httpx import AsyncClient


ADMIN_TOKEN = "test-admin-token-with-at-least-32-characters"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def project_payload(project_id: str = "monitored-api") -> dict:
    return {
        "id": project_id,
        "name": "Monitored API",
        "redaction_policy_version": "default-v1",
        "repositories": [
            {
                "id": "repo-main",
                "locator": f"https://example.invalid/{project_id}.git",
            }
        ],
    }


async def create_project(client: AsyncClient, project_id: str = "monitored-api") -> dict:
    response = await client.post(
        "/api/projects",
        headers=auth(ADMIN_TOKEN),
        json=project_payload(project_id),
    )
    assert response.status_code == 201, response.text
    return response.json()


def event_payload(
    event_id: str,
    *,
    project_id: str = "monitored-api",
    occurred_at: str = "2026-07-14T03:00:10Z",
    order_id: str = "12345",
    request_id: str = "550e8400-e29b-41d4-a716-446655440000",
    line: int = 41,
    repository: bool = True,
    severity: str = "error",
    error_type: str = "InventoryTimeout",
) -> dict:
    payload = {
        "event_id": event_id,
        "project_id": project_id,
        "occurred_at": occurred_at,
        "environment": "production",
        "component": "checkout-api",
        "severity": severity,
        "error": {
            "type": error_type,
            "message": (
                f"Reservation {order_id} failed at {occurred_at} token=event-secret-{order_id}"
            ),
            "stack": [
                f'File "/app/src/inventory/client.py", line {line}, in reserve',
                f"Timeout for request {request_id}",
            ],
        },
        "source": {
            "adapter": "opentelemetry",
            "locator": "otel://monitored-api/checkout-api",
            "selector": f"request_id={request_id} token=selector-secret",
        },
        "service": {"name": "checkout-api", "version": "2026.07.14"},
        "correlation": {"request_id": request_id},
        "release": {
            "deployment_id": "deploy-20260714",
            "deployed_at": "2026-07-14T02:50:00Z",
            "image_digest": f"sha256:{'a' * 64}",
        },
        "attributes": {
            "route": "/checkout",
            "authorization": "Bearer attribute-secret",
        },
    }
    if repository:
        payload["repository"] = {
            "repository_id": "repo-main",
            "commit_sha": "1" * 40,
            "branch": "main",
        }
    return payload


async def test_events_are_deduplicated_grouped_and_open_one_case(client: AsyncClient) -> None:
    project = await create_project(client)
    intake_token = project["credentials"]["intake_token"]
    agent_token = project["credentials"]["agent_token"]

    first_payload = event_payload("event-1")
    first_response = await client.post(
        "/api/events",
        headers=auth(intake_token),
        json=first_payload,
    )
    assert first_response.status_code == 202, first_response.text
    first = first_response.json()
    assert first["accepted"] is True
    assert first["duplicate"] is False
    assert first["detection"] == "first_actionable_event"
    assert first["case_id"].startswith("ISSUE-")
    assert first["group"]["occurrence_count"] == 1
    assert first["group"]["detection_status"] == "case_opened"
    group_id = first["group"]["id"]
    case_id = first["case_id"]

    duplicate_response = await client.post(
        "/api/events",
        headers=auth(intake_token),
        json=first_payload,
    )
    assert duplicate_response.status_code == 200, duplicate_response.text
    duplicate = duplicate_response.json()
    assert duplicate["accepted"] is False
    assert duplicate["duplicate"] is True
    assert duplicate["group"]["occurrence_count"] == 1
    assert duplicate["group"]["id"] == group_id
    assert duplicate["case_id"] == case_id

    conflicting = event_payload("event-1")
    conflicting["attributes"]["attempt"] = 2
    conflict_response = await client.post(
        "/api/events",
        headers=auth(intake_token),
        json=conflicting,
    )
    assert conflict_response.status_code == 409
    assert conflict_response.json()["error"]["code"] == "EVENT_ID_CONFLICT"

    second_response = await client.post(
        "/api/events",
        headers=auth(intake_token),
        json=event_payload(
            "event-2",
            occurred_at="2026-07-14T03:00:40Z",
            order_id="98765",
            request_id="550e8400-e29b-41d4-a716-446655440001",
            line=3142,
        ),
    )
    assert second_response.status_code == 202, second_response.text
    second = second_response.json()
    assert second["group"]["id"] == group_id
    assert second["group"]["occurrence_count"] == 2
    assert second["case_id"] == case_id
    assert second["detection"] == "none"

    third_response = await client.post(
        "/api/events",
        headers=auth(intake_token),
        json=event_payload(
            "event-3",
            occurred_at="2026-07-14T03:01:05Z",
            order_id="45678",
            request_id="550e8400-e29b-41d4-a716-446655440002",
            line=73,
        ),
    )
    assert third_response.status_code == 202, third_response.text
    assert third_response.json()["group"]["occurrence_count"] == 3

    group_response = await client.get(
        f"/api/error-groups/{group_id}",
        headers=auth(agent_token),
    )
    assert group_response.status_code == 200, group_response.text
    group = group_response.json()
    assert group["occurrence_count"] == 3
    assert [bucket["occurrence_count"] for bucket in group["buckets"]] == [2, 1]
    serialized_group = json.dumps(group)
    for secret in ("event-secret", "selector-secret", "attribute-secret"):
        assert secret not in serialized_group
    assert "[REDACTED]" in serialized_group
    assert "12345" not in group["normalized_message"]
    assert group["sample_hash"].startswith("sha256:")

    intake_detail = await client.get(
        f"/api/error-groups/{group_id}",
        headers=auth(intake_token),
    )
    assert intake_detail.status_code == 403

    intake_list = await client.get(
        "/api/error-groups",
        headers=auth(intake_token),
        params={"project_id": "monitored-api"},
    )
    assert intake_list.status_code == 403

    list_response = await client.get(
        "/api/error-groups",
        headers=auth(agent_token),
        params={"project_id": "monitored-api", "severity": "error"},
    )
    assert list_response.status_code == 200, list_response.text
    assert [item["id"] for item in list_response.json()["items"]] == [group_id]

    issue_response = await client.get(
        f"/api/issues/{case_id}",
        headers=auth(agent_token),
    )
    assert issue_response.status_code == 200, issue_response.text
    issue = issue_response.json()
    assert issue["fingerprint"] == group["fingerprint"]
    assert issue["repositories"][0]["commit_sha"] == "1" * 40
    assert "auto-detected" in issue["labels"]
    assert len(issue["evidence"]) == 1

    evidence_id = issue["evidence"][0]["id"]
    evidence_response = await client.get(
        f"/api/issues/{case_id}/evidence/{evidence_id}/content",
        headers=auth(agent_token),
    )
    assert evidence_response.status_code == 200
    for secret in ("event-secret", "selector-secret", "attribute-secret"):
        assert secret not in evidence_response.text

    bundle_response = await client.get(
        f"/api/issues/{case_id}/bundle",
        headers=auth(agent_token),
    )
    assert bundle_response.status_code == 200, bundle_response.text
    with ZipFile(BytesIO(bundle_response.content)) as archive:
        bundle = archive.read("bundle.json")
        evidence_content = archive.read(issue["evidence"][0]["id"].join(["evidence/", ".json"]))
    for secret in (b"event-secret", b"selector-secret", b"attribute-secret"):
        assert secret not in bundle
        assert secret not in evidence_content


async def test_group_waits_for_revision_then_opens_case(client: AsyncClient) -> None:
    project = await create_project(client)
    intake_token = project["credentials"]["intake_token"]

    no_revision = await client.post(
        "/api/events",
        headers=auth(intake_token),
        json=event_payload("event-no-revision", repository=False),
    )
    assert no_revision.status_code == 202, no_revision.text
    first = no_revision.json()
    assert first["case_id"] is None
    assert first["group"]["detection_status"] == "awaiting_revision"

    with_revision = await client.post(
        "/api/events",
        headers=auth(intake_token),
        json=event_payload(
            "event-with-revision",
            occurred_at="2026-07-14T03:00:30Z",
            order_id="98765",
            request_id="550e8400-e29b-41d4-a716-446655440001",
            line=42,
        ),
    )
    assert with_revision.status_code == 202, with_revision.text
    second = with_revision.json()
    assert second["group"]["id"] == first["group"]["id"]
    assert second["group"]["occurrence_count"] == 2
    assert second["case_id"].startswith("ISSUE-")
    assert second["detection"] == "first_actionable_event"


async def test_event_scope_repository_and_size_are_enforced(client: AsyncClient) -> None:
    first = await create_project(client, "project-one")
    second = await create_project(client, "project-two")

    cross_project = await client.post(
        "/api/events",
        headers=auth(first["credentials"]["intake_token"]),
        json=event_payload("cross-project", project_id="project-two"),
    )
    assert cross_project.status_code == 403

    agent_write = await client.post(
        "/api/events",
        headers=auth(first["credentials"]["agent_token"]),
        json=event_payload("agent-write", project_id="project-one"),
    )
    assert agent_write.status_code == 403

    invalid_repository = event_payload("bad-repository", project_id="project-one")
    invalid_repository["repository"]["repository_id"] = "repo-missing"
    repository_response = await client.post(
        "/api/events",
        headers=auth(first["credentials"]["intake_token"]),
        json=invalid_repository,
    )
    assert repository_response.status_code == 422
    assert repository_response.json()["error"]["code"] == "REPOSITORY_NOT_REGISTERED"

    oversized = event_payload("oversized", project_id="project-one")
    oversized["attributes"]["payload"] = "x" * (300 * 1024)
    oversized_response = await client.post(
        "/api/events",
        headers=auth(first["credentials"]["intake_token"]),
        json=oversized,
    )
    assert oversized_response.status_code == 413
    assert oversized_response.json()["error"]["code"] == "EVENT_TOO_LARGE"

    groups = await client.get(
        "/api/error-groups",
        headers=auth(second["credentials"]["agent_token"]),
        params={"project_id": "project-two"},
    )
    assert groups.status_code == 200
    assert groups.json()["items"] == []


async def test_concurrent_delivery_keeps_counts_and_case_unique(client: AsyncClient) -> None:
    project = await create_project(client)
    intake_token = project["credentials"]["intake_token"]
    agent_token = project["credentials"]["agent_token"]

    same_event = event_payload("concurrent-duplicate")
    duplicate_responses = await asyncio.gather(
        *[
            client.post(
                "/api/events",
                headers=auth(intake_token),
                json=same_event,
            )
            for _ in range(8)
        ]
    )
    assert sorted(response.status_code for response in duplicate_responses) == [
        200,
        200,
        200,
        200,
        200,
        200,
        200,
        202,
    ]
    duplicate_bodies = [response.json() for response in duplicate_responses]
    assert sum(body["accepted"] for body in duplicate_bodies) == 1
    assert len({body["group"]["id"] for body in duplicate_bodies}) == 1
    assert len({body["case_id"] for body in duplicate_bodies}) == 1

    equivalent_responses = await asyncio.gather(
        *[
            client.post(
                "/api/events",
                headers=auth(intake_token),
                json=event_payload(
                    f"concurrent-{index}",
                    order_id=str(10000 + index),
                    request_id=f"550e8400-e29b-41d4-a716-{446655440100 + index:012d}",
                    line=100 + index,
                ),
            )
            for index in range(12)
        ]
    )
    assert all(response.status_code == 202 for response in equivalent_responses)
    bodies = [response.json() for response in equivalent_responses]
    group_ids = {body["group"]["id"] for body in bodies}
    case_ids = {body["case_id"] for body in bodies}
    assert group_ids == {duplicate_bodies[0]["group"]["id"]}
    assert case_ids == {duplicate_bodies[0]["case_id"]}
    assert all(body["detection"] == "none" for body in bodies)

    group_response = await client.get(
        f"/api/error-groups/{group_ids.pop()}",
        headers=auth(agent_token),
    )
    assert group_response.status_code == 200, group_response.text
    assert group_response.json()["occurrence_count"] == 13
    assert group_response.json()["buckets"][0]["occurrence_count"] == 13
