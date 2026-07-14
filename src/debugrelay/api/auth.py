from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from secrets import compare_digest

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from debugrelay.api.errors import ApiProblem
from debugrelay.config import Settings
from debugrelay.database import get_session
from debugrelay.models import ProjectRow


bearer_scheme = HTTPBearer(auto_error=False)


class AuthScope(StrEnum):
    admin = "admin"
    intake = "intake"
    agent = "agent"


@dataclass(frozen=True)
class AuthContext:
    scope: AuthScope
    project_id: str | None = None


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


async def get_auth_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiProblem(
            status_code=401,
            code="AUTH_REQUIRED",
            message="A bearer token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    settings: Settings = request.app.state.settings
    if compare_digest(token, settings.effective_admin_token):
        return AuthContext(scope=AuthScope.admin)

    token_hash = hash_token(token)
    project = await session.scalar(
        select(ProjectRow).where(
            or_(
                ProjectRow.intake_token_hash == token_hash,
                ProjectRow.agent_token_hash == token_hash,
            )
        )
    )
    if project is None:
        raise ApiProblem(
            status_code=401,
            code="AUTH_INVALID",
            message="The bearer token is invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if compare_digest(project.intake_token_hash, token_hash):
        return AuthContext(scope=AuthScope.intake, project_id=project.id)
    return AuthContext(scope=AuthScope.agent, project_id=project.id)


def require_scope(
    auth: AuthContext,
    *,
    allowed: set[AuthScope],
    project_id: str | None = None,
) -> None:
    if auth.scope not in allowed:
        raise ApiProblem(
            status_code=403,
            code="AUTH_FORBIDDEN",
            message="The token does not have permission for this operation",
        )
    if auth.scope != AuthScope.admin and project_id is not None and auth.project_id != project_id:
        raise ApiProblem(
            status_code=403,
            code="PROJECT_SCOPE_MISMATCH",
            message="The token is scoped to another project",
        )
