from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import case, false, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from debugrelay.api.auth import hash_token
from debugrelay.api.errors import ApiProblem
from debugrelay.api.schemas import (
    AnalysisCreate,
    Citation,
    EvidenceCreate,
    IssueCreate,
    ProjectCreate,
    ResolutionCreate,
    SourceLocation,
)
from debugrelay.config import Settings
from debugrelay.models import (
    AgentAnalysisRow,
    EvidenceRow,
    IssueRepositoryRow,
    IssueRow,
    ProjectRow,
    RepositoryRow,
    ResolutionRow,
)
from debugrelay.services.redaction import sanitize_json, sanitize_text, serialize_sanitized_content


ISSUE_LOAD_OPTIONS = (
    selectinload(IssueRow.repositories),
    selectinload(IssueRow.evidence),
    selectinload(IssueRow.analyses),
    selectinload(IssueRow.resolution),
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def public_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def ensure_repository_locator_is_safe(locator: str) -> None:
    parsed = urlsplit(locator)
    if parsed.scheme not in {"https", "ssh", "git", "urn"}:
        raise ApiProblem(
            status_code=422,
            code="REPOSITORY_LOCATOR_INVALID",
            message="Repository locator must use https, ssh, git, or urn",
        )
    if parsed.password is not None or (parsed.scheme == "https" and parsed.username is not None):
        raise ApiProblem(
            status_code=422,
            code="REPOSITORY_LOCATOR_CREDENTIALS",
            message="Repository locators must not contain credentials",
        )


async def create_project(
    session: AsyncSession,
    body: ProjectCreate,
    settings: Settings,
) -> tuple[ProjectRow, str, str]:
    for repository in body.repositories:
        ensure_repository_locator_is_safe(repository.locator)

    intake_token = f"dr_intake_{token_urlsafe(settings.token_bytes)}"
    agent_token = f"dr_agent_{token_urlsafe(settings.token_bytes)}"
    project = ProjectRow(
        id=body.id,
        name=body.name,
        redaction_policy_version=body.redaction_policy_version,
        intake_token_hash=hash_token(intake_token),
        agent_token_hash=hash_token(agent_token),
        repositories=[
            RepositoryRow(public_id=repository.id, locator=repository.locator)
            for repository in body.repositories
        ],
    )
    session.add(project)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiProblem(
            status_code=409,
            code="PROJECT_EXISTS",
            message="A project or token with the same identity already exists",
        ) from exc
    return project, intake_token, agent_token


async def get_project(session: AsyncSession, project_id: str) -> ProjectRow:
    project = await session.scalar(
        select(ProjectRow)
        .where(ProjectRow.id == project_id)
        .options(selectinload(ProjectRow.repositories))
    )
    if project is None:
        raise ApiProblem(status_code=404, code="PROJECT_NOT_FOUND", message="Project not found")
    return project


def sanitize_issue_text(body: IssueCreate) -> tuple[str, str, str, list[str]]:
    summary, _ = sanitize_text(body.summary)
    expected, _ = sanitize_text(body.expected)
    actual, _ = sanitize_text(body.actual)
    reproduction = [sanitize_text(step)[0] for step in body.reproduction]
    return summary, expected, actual, reproduction


async def build_evidence_row(
    *,
    issue_id: str,
    project: ProjectRow,
    body: EvidenceCreate,
    settings: Settings,
    existing_evidence_ids: set[str],
) -> EvidenceRow:
    missing_derived = set(body.derived_from) - existing_evidence_ids
    if missing_derived:
        raise ApiProblem(
            status_code=422,
            code="EVIDENCE_REFERENCE_INVALID",
            message="Derived evidence references unknown evidence",
            details={"missing": sorted(missing_derived)},
        )

    try:
        sanitized = serialize_sanitized_content(body.content, body.content_type)
    except (TypeError, ValueError) as exc:
        raise ApiProblem(
            status_code=422,
            code="EVIDENCE_CONTENT_INVALID",
            message=str(exc),
        ) from exc
    if len(sanitized.data) > settings.max_evidence_bytes:
        raise ApiProblem(
            status_code=413,
            code="EVIDENCE_TOO_LARGE",
            message="Sanitized evidence exceeds the configured size limit",
            details={"max_bytes": settings.max_evidence_bytes},
        )

    source, source_redactions = sanitize_json(
        body.source.model_dump(mode="json", exclude_none=True)
    )
    attributes, attribute_redactions = sanitize_json(body.attributes)
    summary, summary_redactions = sanitize_text(body.summary)
    observed_from = body.observed_range.from_ if body.observed_range is not None else None
    observed_to = body.observed_range.to if body.observed_range is not None else None

    return EvidenceRow(
        id=public_id("EVIDENCE"),
        issue_id=issue_id,
        kind=body.kind,
        summary=summary,
        observed_at=body.observed_at,
        observed_from=observed_from,
        observed_to=observed_to,
        collected_at=utc_now(),
        source=source,
        relation=body.relation,
        content_type=body.content_type,
        content_hash=f"sha256:{sha256(sanitized.data).hexdigest()}",
        size_bytes=len(sanitized.data),
        content=sanitized.data,
        redaction_status="sanitized",
        redaction_policy_version=project.redaction_policy_version,
        redaction_count=(
            sanitized.redaction_count
            + source_redactions
            + attribute_redactions
            + summary_redactions
        ),
        derived_from=list(body.derived_from),
        artifact_refs=[],
        attributes=attributes,
    )


async def create_issue(
    session: AsyncSession,
    body: IssueCreate,
    settings: Settings,
) -> IssueRow:
    project = await get_project(session, body.project_id)
    registered = {repository.public_id: repository for repository in project.repositories}
    missing_repositories = {
        repository.repository_id for repository in body.repositories
    } - registered.keys()
    if missing_repositories:
        raise ApiProblem(
            status_code=422,
            code="REPOSITORY_NOT_REGISTERED",
            message="Issue references repositories not registered for the project",
            details={"missing": sorted(missing_repositories)},
        )

    summary, expected, actual, reproduction = sanitize_issue_text(body)
    issue_id = public_id("ISSUE")
    service_name = body.service.name if body.service is not None else None
    service_version = body.service.version if body.service is not None else None
    correlation = (
        sanitize_json(body.correlation.model_dump(mode="json", exclude_none=True))[0]
        if body.correlation
        else None
    )
    release = (
        sanitize_json(body.release.model_dump(mode="json", exclude_none=True))[0]
        if body.release
        else None
    )

    issue = IssueRow(
        id=issue_id,
        project_id=project.id,
        environment=body.environment,
        component=body.component,
        state="open",
        occurred_at=body.occurred_at,
        reported_at=utc_now(),
        summary=summary,
        expected=expected,
        actual=actual,
        reproduction=reproduction,
        fingerprint=body.fingerprint,
        labels=list(dict.fromkeys(body.labels)),
        service_name=service_name,
        service_version=service_version,
        correlation=correlation,
        release=release,
        repositories=[
            IssueRepositoryRow(
                repository_id=repository.repository_id,
                role=repository.role,
                locator=registered[repository.repository_id].locator,
                commit_sha=repository.commit_sha,
                branch=repository.branch,
                subdirectory=repository.subdirectory,
            )
            for repository in body.repositories
        ],
    )
    issue.evidence.append(
        await build_evidence_row(
            issue_id=issue_id,
            project=project,
            body=body.evidence,
            settings=settings,
            existing_evidence_ids=set(),
        )
    )
    session.add(issue)
    await session.commit()
    return await get_issue(session, issue.id)


async def get_issue(session: AsyncSession, issue_id: str) -> IssueRow:
    issue = await session.scalar(
        select(IssueRow).where(IssueRow.id == issue_id).options(*ISSUE_LOAD_OPTIONS)
    )
    if issue is None:
        raise ApiProblem(status_code=404, code="ISSUE_NOT_FOUND", message="Issue not found")
    return issue


async def list_issues(
    session: AsyncSession,
    *,
    project_id: str,
    state: str | None,
    limit: int,
) -> list[IssueRow]:
    statement = (
        select(IssueRow)
        .where(IssueRow.project_id == project_id)
        .options(*ISSUE_LOAD_OPTIONS)
        .order_by(IssueRow.occurred_at.desc(), IssueRow.id.desc())
        .limit(limit)
    )
    if state is not None:
        statement = statement.where(IssueRow.state == state)
    return list((await session.scalars(statement)).unique())


async def add_evidence(
    session: AsyncSession,
    *,
    issue: IssueRow,
    body: EvidenceCreate,
    settings: Settings,
) -> EvidenceRow:
    if issue.state == "resolved":
        raise ApiProblem(
            status_code=409,
            code="ISSUE_RESOLVED",
            message="Resolved issues cannot receive new evidence until reopened",
        )
    project = await get_project(session, issue.project_id)
    evidence = await build_evidence_row(
        issue_id=issue.id,
        project=project,
        body=body,
        settings=settings,
        existing_evidence_ids={item.id for item in issue.evidence},
    )
    session.add(evidence)
    await session.commit()
    await session.refresh(evidence)
    return evidence


def validate_source_location(location: SourceLocation, repository_ids: set[str]) -> None:
    if location.repository_id not in repository_ids:
        raise ApiProblem(
            status_code=422,
            code="ANALYSIS_REPOSITORY_INVALID",
            message="Analysis references a repository outside the issue",
            details={"repository_id": location.repository_id},
        )


def validate_citation(citation: Citation, evidence_ids: set[str], repository_ids: set[str]) -> None:
    if citation.kind == "evidence" and citation.evidence_id not in evidence_ids:
        raise ApiProblem(
            status_code=422,
            code="ANALYSIS_EVIDENCE_INVALID",
            message="Analysis references evidence outside the issue",
            details={"evidence_id": citation.evidence_id},
        )
    if citation.kind == "source" and citation.location is not None:
        validate_source_location(citation.location, repository_ids)


def validate_analysis_references(issue: IssueRow, body: AnalysisCreate) -> None:
    evidence_ids = {evidence.id for evidence in issue.evidence}
    repository_ids = {repository.repository_id for repository in issue.repositories}
    for fact in body.facts:
        for citation in fact.citations:
            validate_citation(citation, evidence_ids, repository_ids)
    for hypothesis in body.hypotheses:
        for citation in hypothesis.citations:
            validate_citation(citation, evidence_ids, repository_ids)
        for check in hypothesis.verification_steps:
            missing = set(check.evidence_refs) - evidence_ids
            if missing:
                raise ApiProblem(
                    status_code=422,
                    code="ANALYSIS_EVIDENCE_INVALID",
                    message="Verification step references evidence outside the issue",
                    details={"missing": sorted(missing)},
                )
    for change in body.proposed_changes:
        validate_source_location(change.location, repository_ids)
    for check in body.checks:
        missing = set(check.evidence_refs) - evidence_ids
        if missing:
            raise ApiProblem(
                status_code=422,
                code="ANALYSIS_EVIDENCE_INVALID",
                message="Analysis check references evidence outside the issue",
                details={"missing": sorted(missing)},
            )


async def add_analysis(
    session: AsyncSession,
    *,
    issue: IssueRow,
    body: AnalysisCreate,
) -> AgentAnalysisRow:
    if issue.state == "resolved":
        raise ApiProblem(
            status_code=409,
            code="ISSUE_RESOLVED",
            message="Resolved issues cannot receive a new analysis until reopened",
        )
    validate_analysis_references(issue, body)
    payload, _ = sanitize_json(body.model_dump(mode="json", exclude_none=True))
    analysis = AgentAnalysisRow(
        id=public_id("ANALYSIS"),
        issue_id=issue.id,
        created_at=utc_now(),
        agent=payload["agent"],
        status=payload["status"],
        facts=payload["facts"],
        hypotheses=payload["hypotheses"],
        missing_information=payload["missing_information"],
        proposed_changes=payload["proposed_changes"],
        checks=payload["checks"],
    )
    issue.state = "analyzing"
    session.add(analysis)
    await session.commit()
    await session.refresh(analysis)
    return analysis


def validate_resolution_references(issue: IssueRow, body: ResolutionCreate) -> None:
    analysis_ids = {analysis.id for analysis in issue.analyses}
    if body.analysis_id not in analysis_ids:
        raise ApiProblem(
            status_code=422,
            code="RESOLUTION_ANALYSIS_INVALID",
            message="Resolution references an analysis outside the issue",
        )
    repository_ids = {repository.repository_id for repository in issue.repositories}
    missing_repositories = {fix.repository_id for fix in body.fixes} - repository_ids
    if missing_repositories:
        raise ApiProblem(
            status_code=422,
            code="RESOLUTION_REPOSITORY_INVALID",
            message="Resolution references repositories outside the issue",
            details={"missing": sorted(missing_repositories)},
        )
    evidence_ids = {evidence.id for evidence in issue.evidence}
    missing_evidence = {
        evidence_id
        for verification in body.verification
        for evidence_id in verification.evidence_refs
        if evidence_id not in evidence_ids
    }
    if missing_evidence:
        raise ApiProblem(
            status_code=422,
            code="RESOLUTION_EVIDENCE_INVALID",
            message="Resolution verification references evidence outside the issue",
            details={"missing": sorted(missing_evidence)},
        )


async def resolve_issue(
    session: AsyncSession,
    *,
    issue: IssueRow,
    body: ResolutionCreate,
) -> ResolutionRow:
    if issue.state == "resolved":
        raise ApiProblem(
            status_code=409,
            code="ISSUE_ALREADY_RESOLVED",
            message="Issue is already resolved",
        )
    validate_resolution_references(issue, body)
    payload, _ = sanitize_json(body.model_dump(mode="json", exclude_none=True))
    confirmed_by: dict[str, Any] = {"id": payload["confirmed_by_id"], "kind": "human"}
    if "confirmed_by_display_name" in payload:
        confirmed_by["display_name"] = payload["confirmed_by_display_name"]
    resolution = ResolutionRow(
        issue_id=issue.id,
        human_confirmed=True,
        confirmed_by=confirmed_by,
        confirmed_at=utc_now(),
        analysis_id=payload["analysis_id"],
        root_cause=payload["root_cause"],
        conditions=payload["conditions"],
        fixes=payload["fixes"],
        verification=payload["verification"],
        observed_in_environment=payload["observed_in_environment"],
    )
    issue.state = "resolved"
    session.add(resolution)
    await session.commit()
    await session.refresh(resolution)
    return resolution


async def find_similar_issues(
    session: AsyncSession,
    *,
    issue: IssueRow,
    limit: int,
) -> list[dict[str, Any]]:
    text_similarity = func.similarity(IssueRow.summary, issue.summary)
    fingerprint_match = (
        IssueRow.fingerprint == issue.fingerprint if issue.fingerprint is not None else false()
    )
    score = case((fingerprint_match, 1.0), else_=text_similarity).label("score")
    rows = await session.execute(
        select(IssueRow, ResolutionRow.confirmed_at, score)
        .join(ResolutionRow, ResolutionRow.issue_id == IssueRow.id)
        .where(
            IssueRow.project_id == issue.project_id,
            IssueRow.id != issue.id,
            IssueRow.state == "resolved",
            or_(fingerprint_match, text_similarity >= 0.2),
        )
        .order_by(score.desc(), ResolutionRow.confirmed_at.desc())
        .limit(limit)
    )
    return [
        {
            "issue_id": similar.id,
            "summary": similar.summary,
            "fingerprint": similar.fingerprint,
            "similarity": float(similarity),
            "resolved_at": resolved_at,
        }
        for similar, resolved_at, similarity in rows
    ]
