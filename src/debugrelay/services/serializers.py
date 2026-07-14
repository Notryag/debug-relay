from __future__ import annotations

from typing import Any

from debugrelay.models import (
    AgentAnalysisRow,
    ErrorGroupRow,
    ErrorOccurrenceBucketRow,
    EvidenceRow,
    IssueRow,
    ProjectRow,
    ResolutionRow,
)


def project_view(project: ProjectRow) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "redaction_policy_version": project.redaction_policy_version,
        "repositories": [
            {"id": repository.public_id, "locator": repository.locator}
            for repository in project.repositories
        ],
        "created_at": project.created_at,
    }


def evidence_view(evidence: EvidenceRow) -> dict[str, Any]:
    observed_range = None
    if evidence.observed_from is not None and evidence.observed_to is not None:
        observed_range = {"from": evidence.observed_from, "to": evidence.observed_to}
    return {
        "id": evidence.id,
        "kind": evidence.kind,
        "summary": evidence.summary,
        "observed_at": evidence.observed_at,
        "observed_range": observed_range,
        "collected_at": evidence.collected_at,
        "source": evidence.source,
        "relation": evidence.relation,
        "content_type": evidence.content_type,
        "content_hash": evidence.content_hash,
        "size_bytes": evidence.size_bytes,
        "redaction_status": evidence.redaction_status,
        "redaction_policy_version": evidence.redaction_policy_version,
        "redaction_count": evidence.redaction_count,
        "derived_from": evidence.derived_from,
        "attributes": evidence.attributes,
    }


def analysis_view(analysis: AgentAnalysisRow) -> dict[str, Any]:
    return {
        "id": analysis.id,
        "issue_id": analysis.issue_id,
        "created_at": analysis.created_at,
        "agent": analysis.agent,
        "status": analysis.status,
        "facts": analysis.facts,
        "hypotheses": analysis.hypotheses,
        "missing_information": analysis.missing_information,
        "proposed_changes": analysis.proposed_changes,
        "checks": analysis.checks,
    }


def resolution_view(resolution: ResolutionRow) -> dict[str, Any]:
    return {
        "issue_id": resolution.issue_id,
        "human_confirmed": resolution.human_confirmed,
        "confirmed_by": resolution.confirmed_by,
        "confirmed_at": resolution.confirmed_at,
        "analysis_id": resolution.analysis_id,
        "root_cause": resolution.root_cause,
        "conditions": resolution.conditions,
        "fixes": resolution.fixes,
        "verification": resolution.verification,
        "observed_in_environment": resolution.observed_in_environment,
    }


def issue_view(issue: IssueRow) -> dict[str, Any]:
    service = None
    if issue.service_name is not None:
        service = {"name": issue.service_name}
        if issue.service_version is not None:
            service["version"] = issue.service_version

    return {
        "id": issue.id,
        "project_id": issue.project_id,
        "environment": issue.environment,
        "component": issue.component,
        "state": issue.state,
        "occurred_at": issue.occurred_at,
        "reported_at": issue.reported_at,
        "summary": issue.summary,
        "expected": issue.expected,
        "actual": issue.actual,
        "reproduction": issue.reproduction,
        "repositories": [
            {
                "repository_id": repository.repository_id,
                "role": repository.role,
                "locator": repository.locator,
                "commit_sha": repository.commit_sha,
                "branch": repository.branch,
                "subdirectory": repository.subdirectory,
            }
            for repository in issue.repositories
        ],
        "evidence": [evidence_view(evidence) for evidence in issue.evidence],
        "fingerprint": issue.fingerprint,
        "labels": issue.labels,
        "service": service,
        "correlation": issue.correlation,
        "release": issue.release,
        "analyses": [analysis_view(analysis) for analysis in issue.analyses],
        "resolution": resolution_view(issue.resolution) if issue.resolution is not None else None,
        "created_at": issue.created_at,
        "updated_at": issue.updated_at,
    }


def error_group_detection_status(group: ErrorGroupRow) -> str:
    if group.active_issue is not None:
        return "case_resolved" if group.active_issue.state == "resolved" else "case_opened"
    if group.highest_severity in {"error", "critical"} and group.latest_repository is None:
        return "awaiting_revision"
    return "observing"


def error_group_summary(group: ErrorGroupRow) -> dict[str, Any]:
    return {
        "id": group.id,
        "project_id": group.project_id,
        "environment": group.environment,
        "component": group.component,
        "fingerprint": group.fingerprint,
        "error_type": group.error_type,
        "normalized_message": group.normalized_message,
        "highest_severity": group.highest_severity,
        "first_seen_at": group.first_seen_at,
        "last_seen_at": group.last_seen_at,
        "occurrence_count": group.occurrence_count,
        "latest_source": group.latest_source,
        "latest_repository": group.latest_repository,
        "latest_release": group.latest_release,
        "active_case_id": group.active_issue_id,
        "active_case_state": group.active_issue.state if group.active_issue is not None else None,
        "detection_status": error_group_detection_status(group),
        "redaction_status": group.redaction_status,
        "redaction_policy_version": group.redaction_policy_version,
        "redaction_count": group.redaction_count,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
    }


def error_group_view(
    group: ErrorGroupRow,
    buckets: list[ErrorOccurrenceBucketRow],
) -> dict[str, Any]:
    return {
        **error_group_summary(group),
        "latest_correlation": group.latest_correlation,
        "sample": group.sample,
        "sample_hash": group.sample_hash,
        "buckets": [
            {
                "bucket_start": bucket.bucket_start,
                "occurrence_count": bucket.occurrence_count,
            }
            for bucket in buckets
        ],
    }
