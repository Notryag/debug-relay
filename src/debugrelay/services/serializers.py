from __future__ import annotations

from typing import Any

from debugrelay.models import AgentAnalysisRow, EvidenceRow, IssueRow, ProjectRow, ResolutionRow


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
