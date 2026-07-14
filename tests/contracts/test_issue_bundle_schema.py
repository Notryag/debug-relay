from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "issue-bundle" / "v1" / "schema.json"
EXAMPLES_ROOT = ROOT / "examples" / "issue-bundles"
EXAMPLE_NAMES = ("minimal", "exception", "resolved")


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


SCHEMA = load_json(SCHEMA_PATH)
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


def load_example(name: str) -> tuple[dict[str, Any], Path]:
    bundle_dir = EXAMPLES_ROOT / name
    return load_json(bundle_dir / "bundle.json"), bundle_dir


def assert_schema_valid(bundle: dict[str, Any]) -> None:
    errors = sorted(VALIDATOR.iter_errors(bundle), key=lambda error: list(error.absolute_path))
    messages = [
        f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
        for error in errors
    ]
    assert not errors, "\n".join(messages)


def assert_unique_ids(items: list[dict[str, Any]], *, label: str) -> set[str]:
    identifiers = [item["id"] for item in items]
    assert len(identifiers) == len(set(identifiers)), f"duplicate {label} ID"
    return set(identifiers)


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.removesuffix("Z") + "+00:00")


def assert_source_location(location: dict[str, Any], repository_ids: set[str]) -> None:
    assert location["repository_id"] in repository_ids, (
        "source location references unknown repository"
    )
    if "line_start" in location and "line_end" in location:
        assert location["line_end"] >= location["line_start"], "source line range is reversed"


def assert_citations(
    citations: list[dict[str, Any]],
    *,
    evidence_ids: set[str],
    repository_ids: set[str],
) -> None:
    for citation in citations:
        if citation["kind"] == "evidence":
            assert citation["evidence_id"] in evidence_ids, "citation references unknown evidence"
        else:
            assert_source_location(citation["location"], repository_ids)


def assert_evidence_content(evidence: dict[str, Any], bundle_dir: Path) -> None:
    root = bundle_dir.resolve()
    content_path = (bundle_dir / evidence["content_ref"]).resolve()
    assert content_path.is_relative_to(root), "evidence path escapes bundle directory"
    assert content_path.is_file(), "evidence file does not exist"
    content = content_path.read_bytes()

    assert evidence["size_bytes"] == len(content), "evidence byte size does not match content"
    assert evidence["content_hash"] == f"sha256:{sha256(content).hexdigest()}", (
        "evidence hash does not match content"
    )


def assert_bundle_semantics(bundle: dict[str, Any], bundle_dir: Path) -> None:
    repository_ids = assert_unique_ids(bundle["repositories"], label="repository")
    evidence_ids = assert_unique_ids(bundle["evidence"], label="evidence")
    artifact_ids = assert_unique_ids(bundle.get("artifacts", []), label="artifact")
    analysis_ids = assert_unique_ids(bundle.get("analyses", []), label="analysis")

    assert set(bundle["issue"]["evidence_refs"]) <= evidence_ids, (
        "issue references unknown evidence"
    )

    for evidence in bundle["evidence"]:
        derived_from = set(evidence.get("derived_from", []))
        assert derived_from <= evidence_ids, "derived evidence references unknown evidence"
        assert evidence["id"] not in derived_from, "evidence cannot derive from itself"
        assert set(evidence.get("artifact_refs", [])) <= artifact_ids, (
            "evidence references unknown artifact"
        )
        if "observed_range" in evidence:
            observed_range = evidence["observed_range"]
            assert parse_utc(observed_range["to"]) >= parse_utc(observed_range["from"]), (
                "evidence time range is reversed"
            )
        assert_evidence_content(evidence, bundle_dir)

    for artifact in bundle.get("artifacts", []):
        root = bundle_dir.resolve()
        artifact_path = (bundle_dir / artifact["content_ref"]).resolve()
        assert artifact_path.is_relative_to(root), "artifact path escapes bundle directory"
        assert artifact_path.is_file(), "artifact file does not exist"
        content = artifact_path.read_bytes()
        assert artifact["size_bytes"] == len(content), "artifact byte size does not match content"
        assert artifact["content_hash"] == f"sha256:{sha256(content).hexdigest()}", (
            "artifact hash does not match content"
        )

    for analysis in bundle.get("analyses", []):
        assert_unique_ids(analysis["facts"], label="fact")
        assert_unique_ids(analysis["hypotheses"], label="hypothesis")
        ranks = [hypothesis["rank"] for hypothesis in analysis["hypotheses"]]
        assert len(ranks) == len(set(ranks)), "hypothesis ranks must be unique"

        for fact in analysis["facts"]:
            assert_citations(
                fact["citations"],
                evidence_ids=evidence_ids,
                repository_ids=repository_ids,
            )
        for hypothesis in analysis["hypotheses"]:
            assert_citations(
                hypothesis["citations"],
                evidence_ids=evidence_ids,
                repository_ids=repository_ids,
            )
            for check in hypothesis["verification_steps"]:
                assert set(check.get("evidence_refs", [])) <= evidence_ids, (
                    "verification step references unknown evidence"
                )
        for proposed_change in analysis["proposed_changes"]:
            assert_source_location(proposed_change["location"], repository_ids)
        for check in analysis["checks"]:
            assert set(check.get("evidence_refs", [])) <= evidence_ids, (
                "analysis check references unknown evidence"
            )

    resolution = bundle.get("resolution")
    if resolution is not None:
        assert resolution["analysis_id"] in analysis_ids, "resolution references unknown analysis"
        for fix in resolution["fixes"]:
            assert fix["repository_id"] in repository_ids, "fix references unknown repository"
        for verification in resolution["verification"]:
            assert set(verification.get("evidence_refs", [])) <= evidence_ids, (
                "resolution verification references unknown evidence"
            )


def assert_schema_rejects(bundle: dict[str, Any]) -> None:
    assert list(VALIDATOR.iter_errors(bundle)), "schema unexpectedly accepted invalid bundle"


def test_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("name", EXAMPLE_NAMES)
def test_example_bundle_is_valid(name: str) -> None:
    bundle, bundle_dir = load_example(name)
    assert_schema_valid(bundle)
    assert_bundle_semantics(bundle, bundle_dir)


def test_schema_rejects_unknown_major_version() -> None:
    bundle, _ = load_example("minimal")
    bundle["schema_version"] = "debugrelay.issue-bundle/v2"
    assert_schema_rejects(bundle)


def test_schema_requires_utc_timestamps() -> None:
    bundle, _ = load_example("minimal")
    bundle["generated_at"] = "2026-07-14T10:05:00+08:00"
    assert_schema_rejects(bundle)


def test_schema_requires_immutable_repository_revision() -> None:
    bundle, _ = load_example("minimal")
    bundle["repositories"][0]["commit_sha"] = "main"
    assert_schema_rejects(bundle)


def test_schema_rejects_unsanitized_bundle() -> None:
    bundle, _ = load_example("minimal")
    bundle["redaction_status"] = "raw"
    assert_schema_rejects(bundle)


def test_schema_rejects_evidence_path_traversal() -> None:
    bundle, _ = load_example("minimal")
    bundle["evidence"][0]["content_ref"] = "../private.env"
    assert_schema_rejects(bundle)


def test_schema_rejects_unknown_top_level_fields() -> None:
    bundle, _ = load_example("minimal")
    bundle["provider_specific_prompt"] = "not part of the portable contract"
    assert_schema_rejects(bundle)


def test_schema_requires_analysis_and_resolution_for_resolved_issue() -> None:
    bundle, _ = load_example("minimal")
    bundle["issue"]["state"] = "resolved"
    assert_schema_rejects(bundle)


def test_schema_rejects_resolution_on_open_issue() -> None:
    bundle, _ = load_example("resolved")
    bundle["issue"]["state"] = "open"
    assert_schema_rejects(bundle)


def test_semantics_reject_broken_issue_evidence_reference() -> None:
    bundle, bundle_dir = load_example("minimal")
    bundle["issue"]["evidence_refs"] = ["EVIDENCE-MISSING"]
    assert_schema_valid(bundle)
    with pytest.raises(AssertionError, match="issue references unknown evidence"):
        assert_bundle_semantics(bundle, bundle_dir)


def test_semantics_reject_duplicate_evidence_ids() -> None:
    bundle, bundle_dir = load_example("exception")
    duplicate = deepcopy(bundle["evidence"][0])
    duplicate["content_ref"] = bundle["evidence"][1]["content_ref"]
    duplicate["content_hash"] = bundle["evidence"][1]["content_hash"]
    duplicate["size_bytes"] = bundle["evidence"][1]["size_bytes"]
    bundle["evidence"].append(duplicate)
    assert_schema_valid(bundle)
    with pytest.raises(AssertionError, match="duplicate evidence ID"):
        assert_bundle_semantics(bundle, bundle_dir)


def test_semantics_reject_missing_evidence_file() -> None:
    bundle, bundle_dir = load_example("minimal")
    bundle["evidence"][0]["content_ref"] = "evidence/missing.json"
    assert_schema_valid(bundle)
    with pytest.raises(AssertionError, match="evidence file does not exist"):
        assert_bundle_semantics(bundle, bundle_dir)


def test_semantics_reject_evidence_hash_mismatch() -> None:
    bundle, bundle_dir = load_example("minimal")
    bundle["evidence"][0]["content_hash"] = "sha256:" + "f" * 64
    assert_schema_valid(bundle)
    with pytest.raises(AssertionError, match="evidence hash does not match content"):
        assert_bundle_semantics(bundle, bundle_dir)


def test_semantics_reject_unknown_analysis_citation() -> None:
    bundle, bundle_dir = load_example("resolved")
    bundle["analyses"][0]["facts"][0]["citations"][0]["evidence_id"] = "EVIDENCE-MISSING"
    assert_schema_valid(bundle)
    with pytest.raises(AssertionError, match="citation references unknown evidence"):
        assert_bundle_semantics(bundle, bundle_dir)


def test_semantics_reject_reversed_source_range() -> None:
    bundle, bundle_dir = load_example("resolved")
    location = bundle["analyses"][0]["facts"][1]["citations"][0]["location"]
    location["line_start"] = 100
    location["line_end"] = 80
    assert_schema_valid(bundle)
    with pytest.raises(AssertionError, match="source line range is reversed"):
        assert_bundle_semantics(bundle, bundle_dir)


def test_semantics_reject_unknown_resolution_analysis() -> None:
    bundle, bundle_dir = load_example("resolved")
    bundle["resolution"]["analysis_id"] = "ANALYSIS-MISSING"
    assert_schema_valid(bundle)
    with pytest.raises(AssertionError, match="resolution references unknown analysis"):
        assert_bundle_semantics(bundle, bundle_dir)
