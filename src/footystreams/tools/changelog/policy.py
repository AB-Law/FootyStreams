"""The rules a change must satisfy about its change fragments (pure; no git, no file access)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.tools.changelog.fragment import Fragment, Impact

FRAGMENT_PREFIX = "changes/unreleased/"
# Paths whose changes never need a fragment of their own (generated or bookkeeping files).
EXEMPT_PREFIXES = (
    "changes/",
    "CHANGELOG.md",
    "release-notes/",
    "docs/milestones/",
    "docs/status.md",
    "README.md",
    "uv.lock",
)
GOLDEN_PREFIX = "tests/golden/"
SCHEMAS_PREFIX = "schemas/"


@dataclass(frozen=True)
class ChangedFile:
    """A file touched by a change. `status` is git's letter: A(dded), M(odified), D(eleted)."""

    path: str
    status: str


@dataclass(frozen=True)
class Problem:
    """One broken change-log rule."""

    rule: str
    message: str

    def __str__(self) -> str:
        """Render as `[rule] message`."""
        return f"[{self.rule}] {self.message}"


def is_fragment_path(path: str) -> bool:
    """True for files in changes/unreleased/ that are numbered fragments."""
    name = path.removeprefix(FRAGMENT_PREFIX)
    return path.startswith(FRAGMENT_PREFIX) and name[:4].isdigit() and name.endswith(".md")


def check_change(changed: Sequence[ChangedFile], fragments: Sequence[Fragment]) -> list[Problem]:
    """Check a change: `fragments` are the fragments added or edited by this change."""
    paths = [item.path for item in changed]  # deletions are changes too
    problems: list[Problem] = []
    needs_fragment = any(not path.startswith(EXEMPT_PREFIXES) for path in paths)
    if needs_fragment and not fragments:
        problems.append(
            Problem(
                "fragment-required", "add one with: uv run changelog new --type ... --scope ..."
            )
        )
    if any(path.startswith(GOLDEN_PREFIX) for path in paths):
        problems.extend(_require_impact(fragments, "sim_version_impact", "golden files changed"))
    if any(path.startswith(SCHEMAS_PREFIX) for path in paths):
        problems.extend(_require_impact(fragments, "schema_version_impact", "schemas changed"))
    return problems


def _require_impact(fragments: Sequence[Fragment], field: str, reason: str) -> list[Problem]:
    if any(getattr(fragment, field) is not Impact.NONE for fragment in fragments):
        return []
    return [Problem(field.replace("_", "-"), f"{reason}, so a fragment must set {field}")]
