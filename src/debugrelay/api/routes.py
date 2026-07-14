from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from debugrelay.api.auth import AuthContext, AuthScope, get_auth_context, require_scope
from debugrelay.api.errors import ApiProblem
from debugrelay.api.schemas import (
    AnalysisCreate,
    AnalysisView,
    ErrorEventCreate,
    ErrorEventIngested,
    ErrorGroupList,
    ErrorGroupSummary,
    ErrorGroupView,
    ErrorSeverity,
    EvidenceCreate,
    EvidenceView,
    IssueCreate,
    IssueList,
    IssueState,
    IssueView,
    ProjectCreate,
    ProjectCreated,
    ProjectCredentials,
    ProjectView,
    ResolutionCreate,
    ResolutionView,
    SimilarIssueList,
)
from debugrelay.config import Settings
from debugrelay.database import get_session
from debugrelay.models import EvidenceRow
from debugrelay.services.bundle import build_bundle_archive
from debugrelay.services.serializers import (
    analysis_view,
    error_group_summary,
    error_group_view,
    evidence_view,
    issue_view,
    project_view,
    resolution_view,
)
from debugrelay.services.monitoring import (
    get_error_group,
    get_error_group_buckets,
    ingest_error_event,
    list_error_groups,
)
from debugrelay.services.workflow import (
    add_analysis,
    add_evidence,
    create_issue,
    create_project,
    find_similar_issues,
    get_issue,
    get_project,
    list_issues,
    resolve_issue,
)


router = APIRouter()


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(select(1))
    return {"status": "ok", "database": "ok"}


@router.post("/api/events", response_model=ErrorEventIngested)
async def ingest_event_route(
    body: ErrorEventCreate,
    request: Request,
    response: Response,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> ErrorEventIngested:
    require_scope(
        auth,
        allowed={AuthScope.admin, AuthScope.intake},
        project_id=body.project_id,
    )
    settings: Settings = request.app.state.settings
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > settings.max_event_bytes:
                raise ApiProblem(
                    status_code=413,
                    code="EVENT_TOO_LARGE",
                    message="Event request exceeds the configured size limit",
                    details={"max_bytes": settings.max_event_bytes},
                )
        except ValueError:
            raise ApiProblem(
                status_code=400,
                code="CONTENT_LENGTH_INVALID",
                message="Content-Length must be an integer",
            ) from None
    result = await ingest_error_event(session, body=body, settings=settings)
    response.status_code = status.HTTP_200_OK if result.duplicate else status.HTTP_202_ACCEPTED
    return ErrorEventIngested(
        event_id=result.event_id,
        accepted=result.accepted,
        duplicate=result.duplicate,
        group=ErrorGroupSummary(**error_group_summary(result.group)),
        case_id=result.case_id,
        detection=result.detection,
    )


@router.get("/api/error-groups", response_model=ErrorGroupList)
async def list_error_groups_route(
    project_id: str,
    environment: str | None = None,
    component: str | None = None,
    severity: ErrorSeverity | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> ErrorGroupList:
    require_scope(
        auth,
        allowed={AuthScope.admin, AuthScope.agent},
        project_id=project_id,
    )
    groups = await list_error_groups(
        session,
        project_id=project_id,
        environment=environment,
        component=component,
        severity=severity,
        limit=limit,
    )
    return ErrorGroupList(
        items=[ErrorGroupSummary(**error_group_summary(group)) for group in groups]
    )


@router.get("/api/error-groups/{group_id}", response_model=ErrorGroupView)
async def get_error_group_route(
    group_id: str,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> ErrorGroupView:
    group = await get_error_group(session, group_id)
    require_scope(
        auth,
        allowed={AuthScope.admin, AuthScope.agent},
        project_id=group.project_id,
    )
    buckets = await get_error_group_buckets(session, group_id=group.id)
    return ErrorGroupView(**error_group_view(group, buckets))


@router.post(
    "/api/projects",
    response_model=ProjectCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_route(
    body: ProjectCreate,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> ProjectCreated:
    require_scope(auth, allowed={AuthScope.admin})
    settings: Settings = request.app.state.settings
    project, intake_token, agent_token = await create_project(session, body, settings)
    return ProjectCreated(
        **project_view(project),
        credentials=ProjectCredentials(
            intake_token=intake_token,
            agent_token=agent_token,
        ),
    )


@router.get("/api/projects/{project_id}", response_model=ProjectView)
async def get_project_route(
    project_id: str,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> ProjectView:
    require_scope(
        auth,
        allowed={AuthScope.admin, AuthScope.intake, AuthScope.agent},
        project_id=project_id,
    )
    project = await get_project(session, project_id)
    return ProjectView(**project_view(project))


@router.post(
    "/api/issues",
    response_model=IssueView,
    status_code=status.HTTP_201_CREATED,
)
async def create_issue_route(
    body: IssueCreate,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> IssueView:
    require_scope(
        auth,
        allowed={AuthScope.admin, AuthScope.intake},
        project_id=body.project_id,
    )
    settings: Settings = request.app.state.settings
    issue = await create_issue(session, body, settings)
    return IssueView(**issue_view(issue))


@router.get("/api/issues", response_model=IssueList)
async def list_issues_route(
    project_id: str,
    state: IssueState | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> IssueList:
    require_scope(
        auth,
        allowed={AuthScope.admin, AuthScope.intake, AuthScope.agent},
        project_id=project_id,
    )
    issues = await list_issues(session, project_id=project_id, state=state, limit=limit)
    return IssueList(items=[IssueView(**issue_view(issue)) for issue in issues])


@router.get("/api/issues/{issue_id}", response_model=IssueView)
async def get_issue_route(
    issue_id: str,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> IssueView:
    issue = await get_issue(session, issue_id)
    require_scope(
        auth,
        allowed={AuthScope.admin, AuthScope.intake, AuthScope.agent},
        project_id=issue.project_id,
    )
    return IssueView(**issue_view(issue))


@router.post(
    "/api/issues/{issue_id}/evidence",
    response_model=EvidenceView,
    status_code=status.HTTP_201_CREATED,
)
async def add_evidence_route(
    issue_id: str,
    body: EvidenceCreate,
    request: Request,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> EvidenceView:
    issue = await get_issue(session, issue_id)
    require_scope(
        auth,
        allowed={AuthScope.admin, AuthScope.intake},
        project_id=issue.project_id,
    )
    settings: Settings = request.app.state.settings
    evidence = await add_evidence(session, issue=issue, body=body, settings=settings)
    return EvidenceView(**evidence_view(evidence))


@router.get("/api/issues/{issue_id}/evidence", response_model=list[EvidenceView])
async def list_evidence_route(
    issue_id: str,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> list[EvidenceView]:
    issue = await get_issue(session, issue_id)
    require_scope(
        auth,
        allowed={AuthScope.admin, AuthScope.intake, AuthScope.agent},
        project_id=issue.project_id,
    )
    return [EvidenceView(**evidence_view(evidence)) for evidence in issue.evidence]


@router.get("/api/issues/{issue_id}/evidence/{evidence_id}/content")
async def get_evidence_content_route(
    issue_id: str,
    evidence_id: str,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> Response:
    issue = await get_issue(session, issue_id)
    require_scope(
        auth,
        allowed={AuthScope.admin, AuthScope.agent},
        project_id=issue.project_id,
    )
    evidence = await session.scalar(
        select(EvidenceRow).where(
            EvidenceRow.issue_id == issue.id,
            EvidenceRow.id == evidence_id,
        )
    )
    if evidence is None:
        raise ApiProblem(
            status_code=404,
            code="EVIDENCE_NOT_FOUND",
            message="Evidence not found",
        )
    return Response(content=evidence.content, media_type=evidence.content_type)


@router.get("/api/issues/{issue_id}/bundle")
async def export_bundle_route(
    issue_id: str,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> Response:
    issue = await get_issue(session, issue_id)
    require_scope(
        auth,
        allowed={AuthScope.admin, AuthScope.agent},
        project_id=issue.project_id,
    )
    archive = build_bundle_archive(issue)
    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{issue.id}.zip"'},
    )


@router.get("/api/issues/{issue_id}/similar", response_model=SimilarIssueList)
async def similar_issues_route(
    issue_id: str,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> SimilarIssueList:
    issue = await get_issue(session, issue_id)
    require_scope(
        auth,
        allowed={AuthScope.admin, AuthScope.agent},
        project_id=issue.project_id,
    )
    return SimilarIssueList(items=await find_similar_issues(session, issue=issue, limit=limit))


@router.post(
    "/api/issues/{issue_id}/analyses",
    response_model=AnalysisView,
    status_code=status.HTTP_201_CREATED,
)
async def add_analysis_route(
    issue_id: str,
    body: AnalysisCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> AnalysisView:
    issue = await get_issue(session, issue_id)
    require_scope(
        auth,
        allowed={AuthScope.admin, AuthScope.agent},
        project_id=issue.project_id,
    )
    analysis = await add_analysis(session, issue=issue, body=body)
    return AnalysisView(**analysis_view(analysis))


@router.post("/api/issues/{issue_id}/resolve", response_model=ResolutionView)
async def resolve_issue_route(
    issue_id: str,
    body: ResolutionCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: AsyncSession = Depends(get_session),
) -> ResolutionView:
    require_scope(auth, allowed={AuthScope.admin})
    issue = await get_issue(session, issue_id)
    resolution = await resolve_issue(session, issue=issue, body=body)
    return ResolutionView(**resolution_view(resolution))
