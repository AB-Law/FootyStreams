"""A change fragment: one small markdown file describing one change.

Format and rules: changes/README.md. A fragment is YAML frontmatter plus an optional free-text body.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

import yaml

FRONTMATTER_FENCE = "---"
SCOPES = frozenset(
    {
        "domain", "events", "sim", "league", "persistence", "seed", "cli", "tools", "schemas",
        "data", "docs", "ci", "design", "runtime", "verify", "extensions", "analytics",
    }
)  # fmt: skip
MILESTONE_PATTERN = re.compile(r"^(design|M\d{1,2})$")
ID_PATTERN = re.compile(r"^\d{4}$")
MAX_SUMMARY_LENGTH = 160


class ChangeType(StrEnum):
    """What kind of change this is (drives the changelog section)."""

    ADDED = "added"
    CHANGED = "changed"
    FIXED = "fixed"
    REMOVED = "removed"
    DEPRECATED = "deprecated"
    SECURITY = "security"
    PERF = "perf"
    REFACTOR = "refactor"
    TEST = "test"
    DOCS = "docs"
    BUILD = "build"


class Impact(StrEnum):
    """How strongly a change affects a versioned contract (schema or simulation output)."""

    NONE = "none"
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


class FragmentError(ValueError):
    """A fragment file is malformed. The message names the file and the problem."""


@dataclass(frozen=True)
class Fragment:
    """A validated change fragment."""

    id: str
    date: date
    type: ChangeType
    scope: tuple[str, ...]
    milestone: str
    breaking: bool
    schema_version_impact: Impact
    sim_version_impact: Impact
    config_impact: bool
    migration: bool
    summary: str
    body: str = ""


_FIELDS = (
    "id", "date", "type", "scope", "milestone", "breaking", "schema_version_impact",
    "sim_version_impact", "config_impact", "migration", "summary",
)  # fmt: skip


def parse_fragment(text: str, source: str) -> Fragment:
    """Parse and validate fragment text. `source` names the file in error messages."""
    metadata, body = _split_frontmatter(text, source)
    unknown = set(metadata) - set(_FIELDS)
    missing = [name for name in _FIELDS if name not in metadata]
    if unknown or missing:
        raise FragmentError(f"{source}: unknown keys {sorted(unknown)}, missing keys {missing}")
    try:
        return _build(metadata, body)
    except (ValueError, TypeError) as error:
        raise FragmentError(f"{source}: {error}") from error


def _split_frontmatter(text: str, source: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0] != FRONTMATTER_FENCE or FRONTMATTER_FENCE not in lines[1:]:
        raise FragmentError(f"{source}: must start with '---' frontmatter")
    end = lines.index(FRONTMATTER_FENCE, 1)
    # BaseLoader keeps every scalar a string, so "0010" is not read as an octal number.
    metadata = yaml.load("\n".join(lines[1:end]), Loader=yaml.BaseLoader)  # noqa: S506
    if not isinstance(metadata, dict):
        raise FragmentError(f"{source}: frontmatter must be key: value pairs")
    return metadata, "\n".join(lines[end + 1 :]).strip()


def _build(metadata: dict[str, Any], body: str) -> Fragment:
    scope = _scopes(metadata["scope"])
    summary = _summary(metadata["summary"])
    return Fragment(
        id=_matching(str(metadata["id"]), ID_PATTERN, "id"),
        date=_date(metadata["date"]),
        type=ChangeType(metadata["type"]),
        scope=scope,
        milestone=_matching(str(metadata["milestone"]), MILESTONE_PATTERN, "milestone"),
        breaking=_boolean(metadata["breaking"], "breaking"),
        schema_version_impact=Impact(metadata["schema_version_impact"]),
        sim_version_impact=Impact(metadata["sim_version_impact"]),
        config_impact=_boolean(metadata["config_impact"], "config_impact"),
        migration=_boolean(metadata["migration"], "migration"),
        summary=summary,
        body=body,
    )


def _matching(value: str, pattern: re.Pattern[str], name: str) -> str:
    if not pattern.match(value):
        raise ValueError(f"{name} {value!r} does not match {pattern.pattern}")
    return value


def _date(value: object) -> date:
    return date.fromisoformat(str(value))


def _boolean(value: object, name: str) -> bool:
    if value not in {"true", "false"}:
        raise TypeError(f"{name} must be true or false, got {value!r}")
    return value == "true"


def _scopes(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise TypeError("scope must be a non-empty list")
    unknown = sorted(set(map(str, value)) - SCOPES)
    if unknown:
        raise ValueError(f"unknown scope(s) {unknown}; allowed: {sorted(SCOPES)}")
    return tuple(str(item) for item in value)


def _summary(value: object) -> str:
    text = str(value).strip()
    if not text or "\n" in text or len(text) > MAX_SUMMARY_LENGTH:
        raise ValueError(f"summary must be one line of 1-{MAX_SUMMARY_LENGTH} characters")
    return text


def render_fragment(fragment: Fragment) -> str:
    """Render a fragment back to its file format (round-trips with `parse_fragment`)."""
    lines = [
        FRONTMATTER_FENCE,
        f"id: {fragment.id}",
        f"date: {fragment.date.isoformat()}",
        f"type: {fragment.type}",
        f"scope: [{', '.join(fragment.scope)}]",
        f"milestone: {fragment.milestone}",
        f"breaking: {str(fragment.breaking).lower()}",
        f"schema_version_impact: {fragment.schema_version_impact}",
        f"sim_version_impact: {fragment.sim_version_impact}",
        f"config_impact: {str(fragment.config_impact).lower()}",
        f"migration: {str(fragment.migration).lower()}",
        f"summary: {yaml.safe_dump(fragment.summary, width=10_000).splitlines()[0]}",
        FRONTMATTER_FENCE,
    ]
    body = f"{fragment.body}\n" if fragment.body else ""
    return "\n".join(lines) + "\n" + body
