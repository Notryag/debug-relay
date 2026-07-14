from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    redaction_policy_version: Mapped[str] = mapped_column(String(128), nullable=False)
    intake_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    agent_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    repositories: Mapped[list[RepositoryRow]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    issues: Mapped[list[IssueRow]] = relationship(back_populates="project")


class RepositoryRow(Base):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("project_id", "public_id", name="uq_repositories_project_public_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    public_id: Mapped[str] = mapped_column(String(128), nullable=False)
    locator: Mapped[str] = mapped_column(String(2048), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped[ProjectRow] = relationship(back_populates="repositories")


class IssueRow(Base):
    __tablename__ = "issues"
    __table_args__ = (
        CheckConstraint(
            "state IN ('open', 'analyzing', 'resolved')",
            name="ck_issues_state",
        ),
        Index("ix_issues_project_state_occurred", "project_id", "state", "occurred_at"),
        Index("ix_issues_fingerprint", "project_id", "fingerprint"),
        Index(
            "ix_issues_summary_trgm",
            "summary",
            postgresql_using="gin",
            postgresql_ops={"summary": "gin_trgm_ops"},
        ),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    environment: Mapped[str] = mapped_column(String(128), nullable=False)
    component: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    expected: Mapped[str] = mapped_column(Text, nullable=False)
    actual: Mapped[str] = mapped_column(Text, nullable=False)
    reproduction: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    labels: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    service_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    service_version: Mapped[str | None] = mapped_column(String(256), nullable=True)
    correlation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    release: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[ProjectRow] = relationship(back_populates="issues")
    repositories: Mapped[list[IssueRepositoryRow]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="IssueRepositoryRow.role",
    )
    evidence: Mapped[list[EvidenceRow]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="EvidenceRow.collected_at",
    )
    analyses: Mapped[list[AgentAnalysisRow]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AgentAnalysisRow.created_at",
    )
    resolution: Mapped[ResolutionRow | None] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
        lazy="selectin",
        uselist=False,
    )


class IssueRepositoryRow(Base):
    __tablename__ = "issue_repositories"
    __table_args__ = (
        CheckConstraint("role IN ('primary', 'related')", name="ck_issue_repositories_role"),
        UniqueConstraint("issue_id", "repository_id", name="uq_issue_repositories_issue_public_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issue_id: Mapped[str] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_id: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    locator: Mapped[str] = mapped_column(String(2048), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    branch: Mapped[str | None] = mapped_column(String(256), nullable=True)
    subdirectory: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    issue: Mapped[IssueRow] = relationship(back_populates="repositories")


class EvidenceRow(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint(
            "relation IN ('anchor', 'correlated', 'derived', 'historical')",
            name="ck_evidence_relation",
        ),
        CheckConstraint(
            "redaction_status = 'sanitized'",
            name="ck_evidence_redaction_status",
        ),
        CheckConstraint(
            "(observed_at IS NOT NULL AND observed_from IS NULL AND observed_to IS NULL) OR "
            "(observed_at IS NULL AND observed_from IS NOT NULL AND observed_to IS NOT NULL "
            "AND observed_to >= observed_from)",
            name="ck_evidence_observation_time",
        ),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    issue_id: Mapped[str] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    relation: Mapped[str] = mapped_column(String(16), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    redaction_status: Mapped[str] = mapped_column(String(16), nullable=False)
    redaction_policy_version: Mapped[str] = mapped_column(String(128), nullable=False)
    redaction_count: Mapped[int] = mapped_column(nullable=False, default=0)
    derived_from: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    artifact_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    issue: Mapped[IssueRow] = relationship(back_populates="evidence")


class AgentAnalysisRow(Base):
    __tablename__ = "agent_analyses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('incomplete', 'complete')",
            name="ck_agent_analyses_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    issue_id: Mapped[str] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    agent: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    facts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    hypotheses: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    missing_information: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    proposed_changes: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    issue: Mapped[IssueRow] = relationship(back_populates="analyses")


class ResolutionRow(Base):
    __tablename__ = "resolutions"
    __table_args__ = (CheckConstraint("human_confirmed", name="ck_resolutions_human_confirmed"),)

    issue_id: Mapped[str] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"),
        primary_key=True,
    )
    human_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    confirmed_by: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("agent_analyses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    conditions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    fixes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    verification: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    observed_in_environment: Mapped[bool] = mapped_column(Boolean, nullable=False)

    issue: Mapped[IssueRow] = relationship(back_populates="resolution")
