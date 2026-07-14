from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from jsonschema import Draft202012Validator, FormatChecker

from debugrelay.models import EvidenceRow, IssueRow


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "schemas" / "issue-bundle" / "v1" / "schema.json"


def load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open(encoding="utf-8") as file:
        return json.load(file)


BUNDLE_VALIDATOR = Draft202012Validator(load_schema(), format_checker=FormatChecker())


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def evidence_extension(evidence: EvidenceRow) -> str:
    if evidence.content_type == "application/json" or evidence.content_type.endswith("+json"):
        return ".json"
    if evidence.content_type.startswith("text/"):
        return ".txt"
    return ".bin"


def evidence_path(evidence: EvidenceRow) -> str:
    return f"evidence/{evidence.id}{evidence_extension(evidence)}"


def bundle_issue(issue: IssueRow) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": issue.id,
        "project_id": issue.project_id,
        "environment": issue.environment,
        "component": issue.component,
        "state": issue.state,
        "occurred_at": utc_text(issue.occurred_at),
        "reported_at": utc_text(issue.reported_at),
        "summary": issue.summary,
        "expected": issue.expected,
        "actual": issue.actual,
        "reproduction": issue.reproduction,
        "evidence_refs": [evidence.id for evidence in issue.evidence],
    }
    if issue.fingerprint is not None:
        data["fingerprint"] = issue.fingerprint
    if issue.labels:
        data["labels"] = issue.labels
    if issue.service_name is not None:
        data["service"] = {"name": issue.service_name}
        if issue.service_version is not None:
            data["service"]["version"] = issue.service_version
    if issue.correlation:
        data["correlation"] = issue.correlation
    if issue.release:
        data["release"] = issue.release
    return data


def bundle_evidence(evidence: EvidenceRow) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": evidence.id,
        "kind": evidence.kind,
        "summary": evidence.summary,
        "collected_at": utc_text(evidence.collected_at),
        "source": evidence.source,
        "relation": evidence.relation,
        "content_type": evidence.content_type,
        "content_hash": evidence.content_hash,
        "size_bytes": evidence.size_bytes,
        "content_ref": evidence_path(evidence),
        "redaction_status": evidence.redaction_status,
        "redaction_policy_version": evidence.redaction_policy_version,
    }
    if evidence.observed_at is not None:
        data["observed_at"] = utc_text(evidence.observed_at)
    else:
        data["observed_range"] = {
            "from": utc_text(evidence.observed_from),
            "to": utc_text(evidence.observed_to),
        }
    if evidence.derived_from:
        data["derived_from"] = evidence.derived_from
    if evidence.artifact_refs:
        data["artifact_refs"] = evidence.artifact_refs
    if evidence.attributes:
        data["attributes"] = evidence.attributes
    return data


def build_bundle_document(issue: IssueRow) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": "debugrelay.issue-bundle/v1",
        "generated_at": utc_text(datetime.now(timezone.utc)),
        "redaction_status": "sanitized",
        "issue": bundle_issue(issue),
        "repositories": [
            {
                "id": repository.repository_id,
                "role": repository.role,
                "locator": repository.locator,
                "commit_sha": repository.commit_sha,
                **({"branch": repository.branch} if repository.branch is not None else {}),
                **(
                    {"subdirectory": repository.subdirectory}
                    if repository.subdirectory is not None
                    else {}
                ),
            }
            for repository in issue.repositories
        ],
        "evidence": [bundle_evidence(evidence) for evidence in issue.evidence],
    }
    if issue.analyses:
        document["analyses"] = [
            {
                "id": analysis.id,
                "created_at": utc_text(analysis.created_at),
                "agent": analysis.agent,
                "status": analysis.status,
                "facts": analysis.facts,
                "hypotheses": analysis.hypotheses,
                "missing_information": analysis.missing_information,
                "proposed_changes": analysis.proposed_changes,
                "checks": analysis.checks,
            }
            for analysis in issue.analyses
        ]
    if issue.resolution is not None:
        resolution = issue.resolution
        document["resolution"] = {
            "human_confirmed": resolution.human_confirmed,
            "confirmed_by": resolution.confirmed_by,
            "confirmed_at": utc_text(resolution.confirmed_at),
            "analysis_id": resolution.analysis_id,
            "root_cause": resolution.root_cause,
            "conditions": resolution.conditions,
            "fixes": resolution.fixes,
            "verification": resolution.verification,
            "observed_in_environment": resolution.observed_in_environment,
        }
    return document


def validate_bundle_document(document: dict[str, Any]) -> None:
    errors = sorted(
        BUNDLE_VALIDATOR.iter_errors(document),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        messages = [
            f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
            for error in errors
        ]
        raise ValueError("Generated bundle violates Issue Bundle v1:\n" + "\n".join(messages))


def build_bundle_archive(issue: IssueRow) -> bytes:
    document = build_bundle_document(issue)
    validate_bundle_document(document)
    output = BytesIO()
    with ZipFile(output, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "bundle.json",
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        for evidence in issue.evidence:
            archive.writestr(evidence_path(evidence), evidence.content)
        archive.writestr(
            "summary.md",
            (
                f"# {issue.id}: {issue.summary}\n\n"
                f"- Project: `{issue.project_id}`\n"
                f"- Component: `{issue.component}`\n"
                f"- State: `{issue.state}`\n"
                f"- Evidence items: {len(issue.evidence)}\n"
                f"- Agent analyses: {len(issue.analyses)}\n"
            ),
        )
    return output.getvalue()
