from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import re
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from debugrelay.api.errors import ApiProblem
from debugrelay.api.schemas import ErrorEventCreate, EvidenceCreate
from debugrelay.config import Settings
from debugrelay.models import (
    ErrorEventReceiptRow,
    ErrorGroupRow,
    ErrorOccurrenceBucketRow,
    IssueRepositoryRow,
    IssueRow,
    ProjectRow,
    RepositoryRow,
)
from debugrelay.services.redaction import sanitize_json
from debugrelay.services.workflow import build_evidence_row, get_project, public_id, utc_now


TIMESTAMP_PATTERN = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b",
    re.IGNORECASE,
)
UUID_PATTERN = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
HEX_PATTERN = re.compile(r"\b(?:0x[0-9a-f]{8,}|[0-9a-f]{16,})\b", re.IGNORECASE)
LONG_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9])\d{4,}(?![A-Za-z0-9])")
STACK_LINE_PATTERN = re.compile(r"(?i)(\bline\s+)\d+|:(\d+)(?::\d+)?(?=\D|$)")
TEMP_PATH_PATTERN = re.compile(r"/(?:tmp|var/tmp)/[^\s'\"]+")
WHITESPACE_PATTERN = re.compile(r"\s+")

SEVERITY_RANK = {"warning": 1, "error": 2, "critical": 3}
ACTIONABLE_SEVERITIES = {"error", "critical"}


@dataclass(frozen=True)
class IngestResult:
    event_id: str
    accepted: bool
    duplicate: bool
    group: ErrorGroupRow
    case_id: str | None
    detection: str


def normalize_error_text(value: str, *, stack_frame: bool = False) -> str:
    normalized = TIMESTAMP_PATTERN.sub("<timestamp>", value)
    normalized = UUID_PATTERN.sub("<uuid>", normalized)
    normalized = HEX_PATTERN.sub("<hex>", normalized)
    normalized = TEMP_PATH_PATTERN.sub("/tmp/<path>", normalized)
    if stack_frame:
        normalized = STACK_LINE_PATTERN.sub(
            lambda match: f"{match.group(1)}<line>" if match.group(1) else ":<line>",
            normalized,
        )
    normalized = LONG_NUMBER_PATTERN.sub("<number>", normalized)
    return WHITESPACE_PATTERN.sub(" ", normalized).strip()


def event_fingerprint(payload: dict[str, Any]) -> tuple[str, str]:
    error = payload["error"]
    normalized_message = normalize_error_text(str(error["message"]))
    normalized_stack = [
        normalize_error_text(str(frame), stack_frame=True) for frame in error.get("stack", [])[:8]
    ]
    material = {
        "project_id": payload["project_id"],
        "environment": payload["environment"],
        "component": payload["component"],
        "error_type": str(error["type"]).casefold(),
        "message": normalized_message.casefold(),
        "stack": normalized_stack,
    }
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{sha256(canonical).hexdigest()}", normalized_message


def sanitize_event(
    body: ErrorEventCreate,
    settings: Settings,
) -> tuple[dict[str, Any], int, str]:
    sanitized, redaction_count = sanitize_json(body.model_dump(mode="json", exclude_none=True))
    if not isinstance(sanitized, dict):
        raise ApiProblem(
            status_code=422,
            code="EVENT_CONTENT_INVALID",
            message="Sanitized event must be a JSON object",
        )
    try:
        canonical = json.dumps(
            sanitized,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ApiProblem(
            status_code=422,
            code="EVENT_CONTENT_INVALID",
            message="Event contains a value that cannot be stored safely",
        ) from exc
    if len(canonical) > settings.max_event_bytes:
        raise ApiProblem(
            status_code=413,
            code="EVENT_TOO_LARGE",
            message="Sanitized event exceeds the configured size limit",
            details={"max_bytes": settings.max_event_bytes},
        )
    return sanitized, redaction_count, f"sha256:{sha256(canonical).hexdigest()}"


async def _advisory_lock(session: AsyncSession, identity: str) -> None:
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:identity, 0))"),
        {"identity": identity},
    )


def _registered_repository(
    project: ProjectRow,
    body: ErrorEventCreate,
) -> RepositoryRow | None:
    if body.repository is None:
        return None
    repository = next(
        (
            candidate
            for candidate in project.repositories
            if candidate.public_id == body.repository.repository_id
        ),
        None,
    )
    if repository is None:
        raise ApiProblem(
            status_code=422,
            code="REPOSITORY_NOT_REGISTERED",
            message="Event references a repository not registered for the project",
            details={"repository_id": body.repository.repository_id},
        )
    return repository


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


async def _build_automatic_case(
    *,
    session: AsyncSession,
    project: ProjectRow,
    repository: RepositoryRow,
    body: ErrorEventCreate,
    sanitized_event: dict[str, Any],
    group: ErrorGroupRow,
    settings: Settings,
    received_at: datetime,
) -> IssueRow:
    issue_id = public_id("ISSUE")
    error = sanitized_event["error"]
    error_type = str(error["type"])
    message = str(error["message"])
    summary = _truncate(f"{error_type}: {message}", 500)
    repository_payload = sanitized_event["repository"]
    evidence = await build_evidence_row(
        issue_id=issue_id,
        project=project,
        body=EvidenceCreate(
            kind="exception",
            summary=summary,
            observed_at=body.occurred_at,
            source=body.source,
            relation="anchor",
            content_type="application/json",
            content=sanitized_event,
            attributes={
                "error_group_id": group.id,
                "event_id": body.event_id,
                "fingerprint": group.fingerprint,
                "detection": "first_actionable_event",
            },
        ),
        settings=settings,
        existing_evidence_ids=set(),
    )
    service = sanitized_event.get("service") or {}
    issue = IssueRow(
        id=issue_id,
        project_id=project.id,
        environment=body.environment,
        component=body.component,
        state="open",
        occurred_at=body.occurred_at,
        reported_at=received_at,
        summary=summary,
        expected=f"{body.component} operates without this error.",
        actual=message,
        reproduction=["Automatically observed from a runtime error event."],
        fingerprint=group.fingerprint,
        labels=["auto-detected", body.severity],
        service_name=service.get("name"),
        service_version=service.get("version"),
        correlation=sanitized_event.get("correlation"),
        release=sanitized_event.get("release"),
        repositories=[
            IssueRepositoryRow(
                repository_id=body.repository.repository_id,
                role="primary",
                locator=repository.locator,
                commit_sha=body.repository.commit_sha,
                branch=repository_payload.get("branch"),
                subdirectory=None,
            )
        ],
        evidence=[evidence],
    )
    session.add(issue)
    group.active_issue = issue
    return issue


async def get_error_group(session: AsyncSession, group_id: str) -> ErrorGroupRow:
    group = await session.scalar(
        select(ErrorGroupRow)
        .where(ErrorGroupRow.id == group_id)
        .options(selectinload(ErrorGroupRow.active_issue))
    )
    if group is None:
        raise ApiProblem(
            status_code=404,
            code="ERROR_GROUP_NOT_FOUND",
            message="Error group not found",
        )
    return group


async def get_error_group_buckets(
    session: AsyncSession,
    *,
    group_id: str,
    limit: int = 120,
) -> list[ErrorOccurrenceBucketRow]:
    buckets = list(
        await session.scalars(
            select(ErrorOccurrenceBucketRow)
            .where(ErrorOccurrenceBucketRow.group_id == group_id)
            .order_by(ErrorOccurrenceBucketRow.bucket_start.desc())
            .limit(limit)
        )
    )
    buckets.reverse()
    return buckets


async def list_error_groups(
    session: AsyncSession,
    *,
    project_id: str,
    environment: str | None,
    component: str | None,
    severity: str | None,
    limit: int,
) -> list[ErrorGroupRow]:
    statement = (
        select(ErrorGroupRow)
        .where(ErrorGroupRow.project_id == project_id)
        .options(selectinload(ErrorGroupRow.active_issue))
        .order_by(ErrorGroupRow.last_seen_at.desc(), ErrorGroupRow.id.desc())
        .limit(limit)
    )
    if environment is not None:
        statement = statement.where(ErrorGroupRow.environment == environment)
    if component is not None:
        statement = statement.where(ErrorGroupRow.component == component)
    if severity is not None:
        statement = statement.where(ErrorGroupRow.highest_severity == severity)
    return list(await session.scalars(statement))


async def ingest_error_event(
    session: AsyncSession,
    *,
    body: ErrorEventCreate,
    settings: Settings,
) -> IngestResult:
    project = await get_project(session, body.project_id)
    repository = _registered_repository(project, body)
    sanitized_event, redaction_count, content_hash = sanitize_event(body, settings)
    fingerprint, normalized_message = event_fingerprint(sanitized_event)

    await _advisory_lock(session, f"event:{body.project_id}:{body.event_id}")
    receipt = await session.scalar(
        select(ErrorEventReceiptRow).where(
            ErrorEventReceiptRow.project_id == body.project_id,
            ErrorEventReceiptRow.event_id == body.event_id,
        )
    )
    if receipt is not None:
        if receipt.content_hash != content_hash:
            raise ApiProblem(
                status_code=409,
                code="EVENT_ID_CONFLICT",
                message="The event ID was already used for different sanitized content",
            )
        group_id = receipt.group_id
        await session.commit()
        group = await get_error_group(session, group_id)
        return IngestResult(
            event_id=body.event_id,
            accepted=False,
            duplicate=True,
            group=group,
            case_id=group.active_issue_id,
            detection="none",
        )

    await _advisory_lock(
        session,
        f"group:{body.project_id}:{body.environment}:{body.component}:{fingerprint}",
    )
    group = await session.scalar(
        select(ErrorGroupRow)
        .where(
            ErrorGroupRow.project_id == body.project_id,
            ErrorGroupRow.environment == body.environment,
            ErrorGroupRow.component == body.component,
            ErrorGroupRow.fingerprint == fingerprint,
        )
        .options(selectinload(ErrorGroupRow.active_issue))
    )
    received_at = utc_now()
    is_new_group = group is None
    if group is None:
        group = ErrorGroupRow(
            id=public_id("GROUP"),
            project_id=body.project_id,
            environment=body.environment,
            component=body.component,
            fingerprint=fingerprint,
            error_type=str(sanitized_event["error"]["type"]),
            normalized_message=normalized_message,
            highest_severity=body.severity,
            first_seen_at=body.occurred_at,
            last_seen_at=body.occurred_at,
            occurrence_count=1,
            latest_source=sanitized_event["source"],
            latest_repository=sanitized_event.get("repository"),
            latest_release=sanitized_event.get("release"),
            latest_correlation=sanitized_event.get("correlation"),
            sample=sanitized_event,
            sample_hash=content_hash,
            redaction_status="sanitized",
            redaction_policy_version=project.redaction_policy_version,
            redaction_count=redaction_count,
        )
        session.add(group)
    else:
        previous_last_seen = group.last_seen_at
        group.first_seen_at = min(group.first_seen_at, body.occurred_at)
        group.last_seen_at = max(group.last_seen_at, body.occurred_at)
        group.occurrence_count += 1
        if SEVERITY_RANK[body.severity] > SEVERITY_RANK[group.highest_severity]:
            group.highest_severity = body.severity
        if body.occurred_at >= previous_last_seen:
            group.latest_source = sanitized_event["source"]
            group.latest_repository = sanitized_event.get("repository")
            group.latest_release = sanitized_event.get("release")
            group.latest_correlation = sanitized_event.get("correlation")

    bucket_start = body.occurred_at.replace(second=0, microsecond=0)
    bucket = None
    if not is_new_group:
        bucket = await session.get(
            ErrorOccurrenceBucketRow,
            {"group_id": group.id, "bucket_start": bucket_start},
        )
    if bucket is None:
        bucket = ErrorOccurrenceBucketRow(
            group_id=group.id,
            bucket_start=bucket_start,
            occurrence_count=1,
        )
        session.add(bucket)
    else:
        bucket.occurrence_count += 1

    detection = "none"
    if (
        group.active_issue_id is None
        and body.severity in ACTIONABLE_SEVERITIES
        and repository is not None
    ):
        await _build_automatic_case(
            session=session,
            project=project,
            repository=repository,
            body=body,
            sanitized_event=sanitized_event,
            group=group,
            settings=settings,
            received_at=received_at,
        )
        detection = "first_actionable_event"

    session.add(
        ErrorEventReceiptRow(
            project_id=body.project_id,
            event_id=body.event_id,
            group=group,
            occurred_at=body.occurred_at,
            received_at=received_at,
            content_hash=content_hash,
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiProblem(
            status_code=409,
            code="EVENT_INGEST_CONFLICT",
            message="Concurrent event ingestion conflicted with stored monitoring state",
        ) from exc

    group = await get_error_group(session, group.id)

    return IngestResult(
        event_id=body.event_id,
        accepted=True,
        duplicate=False,
        group=group,
        case_id=group.active_issue_id,
        detection=detection,
    )
