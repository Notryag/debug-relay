from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(timezone.utc)


def validate_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("path must stay within the authorized root")
    return value


Identifier = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
]
GitCommit = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}([0-9a-f]{24})?$")]
RelativePath = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=1024,
        pattern=r"^[A-Za-z0-9._/-]+$",
    ),
    AfterValidator(validate_relative_path),
]
UtcDatetime = Annotated[datetime, AfterValidator(normalize_utc)]

IssueState = Literal["open", "analyzing", "resolved"]
EvidenceKind = Literal[
    "user_report",
    "exception",
    "log",
    "request",
    "runtime",
    "change",
    "deployment",
    "test",
    "trace",
    "metric",
    "other",
]
EvidenceRelation = Literal["anchor", "correlated", "derived", "historical"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RepositoryRegistration(ApiModel):
    id: Identifier
    locator: Annotated[str, Field(min_length=1, max_length=2048)]


class ProjectCreate(ApiModel):
    id: Identifier
    name: Annotated[str, Field(min_length=1, max_length=256)]
    redaction_policy_version: Identifier = "default-v1"
    repositories: Annotated[list[RepositoryRegistration], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def repositories_are_unique(self) -> ProjectCreate:
        repository_ids = [repository.id for repository in self.repositories]
        if len(repository_ids) != len(set(repository_ids)):
            raise ValueError("repository IDs must be unique")
        return self


class ProjectCredentials(ApiModel):
    intake_token: str
    agent_token: str


class ProjectView(ApiModel):
    id: str
    name: str
    redaction_policy_version: str
    repositories: list[RepositoryRegistration]
    created_at: datetime


class ProjectCreated(ProjectView):
    credentials: ProjectCredentials


class ServiceIdentity(ApiModel):
    name: Identifier
    version: Annotated[str | None, Field(default=None, min_length=1, max_length=256)]


class Correlation(ApiModel):
    trace_id: Annotated[str | None, Field(default=None, pattern=r"^[0-9a-f]{32}$")]
    span_id: Annotated[str | None, Field(default=None, pattern=r"^[0-9a-f]{16}$")]
    request_id: Annotated[str | None, Field(default=None, min_length=1, max_length=256)]
    job_id: Annotated[str | None, Field(default=None, min_length=1, max_length=256)]

    @model_validator(mode="after")
    def has_a_value(self) -> Correlation:
        if not any((self.trace_id, self.span_id, self.request_id, self.job_id)):
            raise ValueError("correlation must include at least one identifier")
        return self


class ReleaseIdentity(ApiModel):
    deployment_id: Identifier | None = None
    deployed_at: UtcDatetime | None = None
    image_digest: Annotated[
        str | None,
        Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$"),
    ]
    source_map_revision: Annotated[
        str | None,
        Field(default=None, min_length=1, max_length=256),
    ]
    configuration_fingerprints: dict[
        Identifier, Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
    ] = Field(
        default_factory=dict,
        max_length=100,
    )

    @model_validator(mode="after")
    def has_a_value(self) -> ReleaseIdentity:
        if not any(
            (
                self.deployment_id,
                self.deployed_at,
                self.image_digest,
                self.source_map_revision,
                self.configuration_fingerprints,
            )
        ):
            raise ValueError("release must include at least one value")
        return self


class IssueRepositoryInput(ApiModel):
    repository_id: Identifier
    role: Literal["primary", "related"]
    commit_sha: GitCommit
    branch: Annotated[str | None, Field(default=None, min_length=1, max_length=256)]
    subdirectory: RelativePath | None = None


class ObservedRange(ApiModel):
    from_: UtcDatetime = Field(alias="from")
    to: UtcDatetime

    @model_validator(mode="after")
    def ordered(self) -> ObservedRange:
        if self.to < self.from_:
            raise ValueError("observed range is reversed")
        return self


class EvidenceSource(ApiModel):
    adapter: Identifier
    locator: Annotated[str, Field(min_length=1, max_length=2048)]
    selector: Annotated[str | None, Field(default=None, min_length=1, max_length=4096)]
    query: Annotated[str | None, Field(default=None, min_length=1, max_length=4096)]


EvidenceContent = str | dict[str, Any] | list[Any] | int | float | bool


class EvidenceCreate(ApiModel):
    kind: EvidenceKind
    summary: Annotated[str, Field(min_length=1, max_length=500)]
    observed_at: UtcDatetime | None = None
    observed_range: ObservedRange | None = None
    source: EvidenceSource
    relation: EvidenceRelation
    content_type: Annotated[
        str,
        Field(pattern=r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$", max_length=255),
    ]
    content: EvidenceContent
    derived_from: Annotated[list[Identifier], Field(default_factory=list, max_length=100)]
    attributes: dict[str, Any] = Field(default_factory=dict, max_length=100)

    @model_validator(mode="after")
    def one_observation_time(self) -> EvidenceCreate:
        if (self.observed_at is None) == (self.observed_range is None):
            raise ValueError("provide exactly one of observed_at or observed_range")
        return self


class IssueCreate(ApiModel):
    project_id: Identifier
    environment: Identifier
    component: Identifier
    occurred_at: UtcDatetime
    summary: Annotated[str, Field(min_length=1, max_length=500)]
    expected: Annotated[str, Field(min_length=1, max_length=65536)]
    actual: Annotated[str, Field(min_length=1, max_length=65536)]
    reproduction: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=4096)]], Field(max_length=50)
    ]
    repositories: Annotated[list[IssueRepositoryInput], Field(min_length=1, max_length=20)]
    evidence: EvidenceCreate
    fingerprint: Identifier | None = None
    labels: Annotated[list[Identifier], Field(default_factory=list, max_length=50)]
    service: ServiceIdentity | None = None
    correlation: Correlation | None = None
    release: ReleaseIdentity | None = None

    @model_validator(mode="after")
    def repository_roles_are_valid(self) -> IssueCreate:
        repository_ids = [repository.repository_id for repository in self.repositories]
        if len(repository_ids) != len(set(repository_ids)):
            raise ValueError("repository IDs must be unique")
        primary_count = sum(repository.role == "primary" for repository in self.repositories)
        if primary_count != 1:
            raise ValueError("exactly one primary repository is required")
        if self.evidence.relation != "anchor":
            raise ValueError("initial evidence must have the anchor relation")
        if self.evidence.derived_from:
            raise ValueError("initial evidence cannot derive from another evidence item")
        return self


class EvidenceView(ApiModel):
    id: str
    kind: str
    summary: str
    observed_at: datetime | None
    observed_range: dict[str, datetime] | None
    collected_at: datetime
    source: dict[str, Any]
    relation: str
    content_type: str
    content_hash: str
    size_bytes: int
    redaction_status: str
    redaction_policy_version: str
    redaction_count: int
    derived_from: list[str]
    attributes: dict[str, Any]


class IssueView(ApiModel):
    id: str
    project_id: str
    environment: str
    component: str
    state: IssueState
    occurred_at: datetime
    reported_at: datetime
    summary: str
    expected: str
    actual: str
    reproduction: list[str]
    repositories: list[dict[str, Any]]
    evidence: list[EvidenceView]
    fingerprint: str | None
    labels: list[str]
    service: dict[str, Any] | None
    correlation: dict[str, Any] | None
    release: dict[str, Any] | None
    analyses: list[dict[str, Any]]
    resolution: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class IssueList(ApiModel):
    items: list[IssueView]


class SourceLocation(ApiModel):
    repository_id: Identifier
    path: RelativePath
    symbol: Annotated[str | None, Field(default=None, min_length=1, max_length=512)]
    line_start: Annotated[int | None, Field(default=None, ge=1)]
    line_end: Annotated[int | None, Field(default=None, ge=1)]

    @model_validator(mode="after")
    def ordered_lines(self) -> SourceLocation:
        if self.line_start is None and self.line_end is not None:
            raise ValueError("line_end requires line_start")
        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_end < self.line_start
        ):
            raise ValueError("source line range is reversed")
        return self


class Citation(ApiModel):
    kind: Literal["evidence", "source"]
    evidence_id: Identifier | None = None
    location: SourceLocation | None = None

    @model_validator(mode="after")
    def matches_kind(self) -> Citation:
        if self.kind == "evidence" and (self.evidence_id is None or self.location is not None):
            raise ValueError("evidence citation requires only evidence_id")
        if self.kind == "source" and (self.location is None or self.evidence_id is not None):
            raise ValueError("source citation requires only location")
        return self


class FactInput(ApiModel):
    id: Identifier
    statement: Annotated[str, Field(min_length=1, max_length=65536)]
    citations: Annotated[list[Citation], Field(min_length=1, max_length=50)]


class CheckInput(ApiModel):
    id: Identifier
    description: Annotated[str, Field(min_length=1, max_length=65536)]
    command: Annotated[str | None, Field(default=None, min_length=1, max_length=8192)]
    status: Literal["proposed", "passed", "failed", "skipped"]
    result: Annotated[str | None, Field(default=None, min_length=1, max_length=65536)]
    evidence_refs: Annotated[list[Identifier], Field(default_factory=list, max_length=100)]


class HypothesisInput(ApiModel):
    id: Identifier
    rank: Annotated[int, Field(ge=1)]
    statement: Annotated[str, Field(min_length=1, max_length=65536)]
    status: Literal["unconfirmed", "supported", "rejected"]
    citations: Annotated[list[Citation], Field(min_length=1, max_length=50)]
    verification_steps: Annotated[list[CheckInput], Field(min_length=1, max_length=50)]


class ProposedChangeInput(ApiModel):
    location: SourceLocation
    summary: Annotated[str, Field(min_length=1, max_length=65536)]


class AgentIdentity(ApiModel):
    name: Identifier
    version: Annotated[str | None, Field(default=None, min_length=1, max_length=128)]
    provider: Annotated[str | None, Field(default=None, min_length=1, max_length=128)]
    model: Annotated[str | None, Field(default=None, min_length=1, max_length=256)]


class AnalysisCreate(ApiModel):
    agent: AgentIdentity
    status: Literal["incomplete", "complete"]
    facts: Annotated[list[FactInput], Field(min_length=1, max_length=200)]
    hypotheses: Annotated[list[HypothesisInput], Field(min_length=1, max_length=50)]
    missing_information: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=500)]],
        Field(default_factory=list, max_length=100),
    ]
    proposed_changes: Annotated[
        list[ProposedChangeInput], Field(default_factory=list, max_length=100)
    ]
    checks: Annotated[list[CheckInput], Field(default_factory=list, max_length=100)]

    @model_validator(mode="after")
    def identifiers_are_unique(self) -> AnalysisCreate:
        for label, values in (
            ("fact", [fact.id for fact in self.facts]),
            ("hypothesis", [hypothesis.id for hypothesis in self.hypotheses]),
            ("hypothesis rank", [str(hypothesis.rank) for hypothesis in self.hypotheses]),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{label} values must be unique")
        return self


class AnalysisView(ApiModel):
    id: str
    issue_id: str
    created_at: datetime
    agent: dict[str, Any]
    status: str
    facts: list[dict[str, Any]]
    hypotheses: list[dict[str, Any]]
    missing_information: list[str]
    proposed_changes: list[dict[str, Any]]
    checks: list[dict[str, Any]]


class FileChangeInput(ApiModel):
    path: RelativePath
    summary: Annotated[str, Field(min_length=1, max_length=500)]


class FixInput(ApiModel):
    repository_id: Identifier
    commit_sha: GitCommit
    changed_files: Annotated[list[FileChangeInput], Field(min_length=1, max_length=500)]


class VerificationInput(ApiModel):
    id: Identifier
    description: Annotated[str, Field(min_length=1, max_length=65536)]
    command: Annotated[str | None, Field(default=None, min_length=1, max_length=8192)]
    status: Literal["passed"] = "passed"
    result: Annotated[str, Field(min_length=1, max_length=65536)]
    verified_at: UtcDatetime
    evidence_refs: Annotated[list[Identifier], Field(default_factory=list, max_length=100)]


class ResolutionCreate(ApiModel):
    confirmed_by_id: Identifier
    confirmed_by_display_name: Annotated[
        str | None,
        Field(default=None, min_length=1, max_length=256),
    ]
    analysis_id: Identifier
    root_cause: Annotated[str, Field(min_length=1, max_length=65536)]
    conditions: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=500)]],
        Field(default_factory=list, max_length=50),
    ]
    fixes: Annotated[list[FixInput], Field(min_length=1, max_length=20)]
    verification: Annotated[list[VerificationInput], Field(min_length=1, max_length=100)]
    observed_in_environment: bool


class ResolutionView(ApiModel):
    issue_id: str
    human_confirmed: Literal[True]
    confirmed_by: dict[str, Any]
    confirmed_at: datetime
    analysis_id: str
    root_cause: str
    conditions: list[str]
    fixes: list[dict[str, Any]]
    verification: list[dict[str, Any]]
    observed_in_environment: bool


class SimilarIssue(ApiModel):
    issue_id: str
    summary: str
    fingerprint: str | None
    similarity: float
    resolved_at: datetime


class SimilarIssueList(ApiModel):
    items: list[SimilarIssue]
