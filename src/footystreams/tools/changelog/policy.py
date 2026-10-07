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
SCHEMA_VERSIONS_PATH = "src/footystreams/domain/versions.py"


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


@dataclass(frozen=True)
class SchemaVersionFact:
    """Whether SCHEMA_VERSION changed between base and head (facts only; no I/O here).

    ``base_version`` is None when the versions module did not exist at the base ref
    (first introduction). ``head_version`` is None when the file was deleted.
    """

    path_in_change: bool
    base_version: str | None
    head_version: str | None


def is_fragment_path(path: str) -> bool:
    """True for files in changes/unreleased/ that are numbered fragments."""
    name = path.removeprefix(FRAGMENT_PREFIX)
    return path.startswith(FRAGMENT_PREFIX) and name[:4].isdigit() and name.endswith(".md")


def check_change(
    changed: Sequence[ChangedFile],
    fragments: Sequence[Fragment],
    schema_version: SchemaVersionFact | None = None,
) -> list[Problem]:
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
    schemas_changed = any(path.startswith(SCHEMAS_PREFIX) for path in paths)
    if schemas_changed:
        problems.extend(_require_impact(fragments, "schema_version_impact", "schemas changed"))
        if schema_version is not None:
            problems.extend(_require_schema_version_bump(schema_version))
    return problems


def _require_impact(fragments: Sequence[Fragment], field: str, reason: str) -> list[Problem]:
    if any(getattr(fragment, field) is not Impact.NONE for fragment in fragments):
        return []
    return [Problem(field.replace("_", "-"), f"{reason}, so a fragment must set {field}")]


def _require_schema_version_bump(fact: SchemaVersionFact) -> list[Problem]:
    if fact.base_version is None and fact.head_version is not None:
        # First introduction of the versions module (typical for M1).
        return []
    if not fact.path_in_change:
        return [
            Problem(
                "schema-version-bump",
                f"schemas changed, so bump SCHEMA_VERSION in {SCHEMA_VERSIONS_PATH}",
            )
        ]
    if fact.head_version is None:
        return [Problem("schema-version-bump", f"{SCHEMA_VERSIONS_PATH} must not be deleted")]
    if fact.base_version == fact.head_version:
        return [
            Problem(
                "schema-version-bump",
                f"schemas changed, but SCHEMA_VERSION is still {fact.head_version!r}",
            )
        ]
    return []
