import json
from pathlib import Path

from debugrelay.api.schemas import AnalysisCreate, IssueCreate, ProjectCreate, ResolutionCreate


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "cli"


def load(name: str) -> dict:
    with (EXAMPLES / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def test_cli_request_examples_match_api_models() -> None:
    ProjectCreate.model_validate(load("project-create.json"))
    IssueCreate.model_validate(load("issue-create.json"))
    AnalysisCreate.model_validate(load("analysis-create.json"))
    ResolutionCreate.model_validate(load("resolution-create.json"))
