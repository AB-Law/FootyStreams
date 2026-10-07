"""Guard rails for the CI workflow: it must keep running the same gate developers run locally."""

from pathlib import Path
from typing import Any

import yaml

from footystreams.tools.paths import PROJECT_ROOT

WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"


def _load() -> dict[Any, Any]:
    loaded = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _run_commands(job: dict[str, Any]) -> list[str]:
    return [step["run"] for step in job["steps"] if "run" in step]


def test_ci__runs_on_pull_requests_and_pushes_to_main() -> None:
    triggers = _load()[True]  # YAML 1.1 reads the key `on` as the boolean True

    assert "pull_request" in triggers
    assert triggers["push"]["branches"] == ["main"]


def test_ci__quality_job_covers_both_operating_systems_and_python_versions() -> None:
    matrix = _load()["jobs"]["quality"]["strategy"]["matrix"]

    assert set(matrix["os"]) == {"ubuntu-latest", "windows-latest"}
    assert set(matrix["python"]) == {"3.12", "3.13"}


def test_ci__quality_job_runs_the_pr_tier_gate_with_full_history() -> None:
    job = _load()["jobs"]["quality"]
    checkout = next(
        step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout")
    )

    assert "uv run check --tier pr" in _run_commands(job)
    assert checkout["with"]["fetch-depth"] == 0  # the change-log check needs origin/main


def test_ci__pr_size_job_only_reports_and_never_blocks_milestone_prs() -> None:
    job = _load()["jobs"]["pr-size"]
    command = _run_commands(job)[-1]

    assert job["if"] == "github.event_name == 'pull_request'"
    assert "uv run pr-size" in command
    assert "--allow-large" in command  # one PR per milestone: informational, not a gate


def test_ci__workflow_default_permissions_are_read_only() -> None:
    assert _load()["permissions"] == {"contents": "read"}


def test_codeowners__assigns_everything_to_the_owner() -> None:
    codeowners = Path(PROJECT_ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")

    assert "* @AB-Law" in codeowners.splitlines()
