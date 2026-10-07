from datetime import date
from pathlib import Path

import pytest

from footystreams.tools.changelog.fragment import (
    ChangeType,
    Fragment,
    FragmentError,
    Impact,
    parse_fragment,
    render_fragment,
)
from footystreams.tools.paths import CHANGES_DIR

VALID = """---
id: 0010
date: 2026-10-07
type: added
scope: [sim, events]
milestone: M5
breaking: false
schema_version_impact: none
sim_version_impact: minor
config_impact: true
migration: false
summary: Add offside detection to the pass resolver.
---
Longer explanation.
"""


def _replace(text: str, old: str, new: str) -> str:
    assert old in text
    return text.replace(old, new)


def test_parse_fragment__valid_text__returns_typed_fragment() -> None:
    fragment = parse_fragment(VALID, source="x.md")

    assert fragment == Fragment(
        id="0010",
        date=date(2026, 10, 7),
        type=ChangeType.ADDED,
        scope=("sim", "events"),
        milestone="M5",
        breaking=False,
        schema_version_impact=Impact.NONE,
        sim_version_impact=Impact.MINOR,
        config_impact=True,
        migration=False,
        summary="Add offside detection to the pass resolver.",
        body="Longer explanation.",
    )


def test_parse_fragment__numeric_looking_ids__stay_strings() -> None:
    # YAML would read 0010 as octal 8 and 0009 as a string; ids must be taken literally.
    assert parse_fragment(VALID, "x.md").id == "0010"
    assert parse_fragment(_replace(VALID, "id: 0010", "id: 0009"), "x.md").id == "0009"


def test_render_fragment__round_trips_through_parse_fragment() -> None:
    fragment = parse_fragment(VALID, source="x.md")

    assert parse_fragment(render_fragment(fragment), source="y.md") == fragment


def test_render_fragment__summary_with_yaml_special_characters__round_trips() -> None:
    tricky = _replace(
        VALID, "Add offside detection to the pass resolver.", "'Fix: it''s #1 [done]'"
    )

    fragment = parse_fragment(tricky, "x.md")

    assert fragment.summary == "Fix: it's #1 [done]"
    assert parse_fragment(render_fragment(fragment), "y.md") == fragment


@pytest.mark.parametrize(
    ("old", "new", "problem"),
    [
        ("type: added", "type: invented", "type"),
        ("scope: [sim, events]", "scope: [sim, nonsense]", "scope"),
        ("scope: [sim, events]", "scope: []", "scope"),
        ("milestone: M5", "milestone: Q9", "milestone"),
        ("breaking: false", "breaking: maybe", "breaking"),
        ("sim_version_impact: minor", "sim_version_impact: huge", "impact"),
        ("id: 0010", "id: 10", "id"),
        ("date: 2026-10-07", "date: yesterday", "date"),
        ("summary: Add offside detection to the pass resolver.", "summary: ''", "summary"),
        ("migration: false", "migration: false\nextra: 1", "unknown"),
        ("breaking: false\n", "", "missing"),
    ],
)
def test_parse_fragment__invalid_field__raises_naming_the_file(
    old: str, new: str, problem: str
) -> None:
    with pytest.raises(FragmentError, match=r"bad.md"):
        parse_fragment(_replace(VALID, old, new), source="bad.md")


@pytest.mark.parametrize("text", ["no frontmatter", "---\nid: 1\n", "---\njust text\n---\n"])
def test_parse_fragment__broken_frontmatter__raises(text: str) -> None:
    with pytest.raises(FragmentError, match=r"bad.md"):
        parse_fragment(text, source="bad.md")


def test_repository_fragments__all_parse() -> None:
    paths = sorted((CHANGES_DIR / "unreleased").glob("[0-9][0-9][0-9][0-9]-*.md"))

    assert paths, "expected at least one unreleased fragment in the repository"
    for path in paths:
        fragment = parse_fragment(Path(path).read_text(encoding="utf-8"), source=path.name)
        assert path.name.startswith(fragment.id)
