from datetime import date

import pytest

from footystreams.tools.changelog.build import render_changelog
from footystreams.tools.changelog.fragment import ChangeType, Fragment, Impact
from footystreams.tools.changelog.policy import ChangedFile, check_change, is_fragment_path


def _fragment(
    fragment_id: str = "0001",
    change_type: ChangeType = ChangeType.ADDED,
    *,
    sim: Impact = Impact.NONE,
    schema: Impact = Impact.NONE,
    disruptive: bool = False,
) -> Fragment:
    return Fragment(
        id=fragment_id,
        date=date(2026, 10, 7),
        type=change_type,
        scope=("sim",),
        milestone="M4",
        breaking=disruptive,
        schema_version_impact=schema,
        sim_version_impact=sim,
        config_impact=False,
        migration=disruptive,
        summary=f"Summary {fragment_id}",
    )


def _changed(*paths: str, status: str = "M") -> list[ChangedFile]:
    return [ChangedFile(path, status) for path in paths]


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("changes/unreleased/0007-x.md", True),
        ("changes/unreleased/README.md", False),
        ("changes/released/0.1.0/0007-x.md", False),
        ("src/footystreams/sim/0001-x.md", False),
    ],
)
def test_is_fragment_path(path: str, *, expected: bool) -> None:
    assert is_fragment_path(path) is expected


def test_check_change__only_exempt_files__needs_no_fragment() -> None:
    changed = _changed(
        "CHANGELOG.md", "README.md", "uv.lock", "docs/status.md", "changes/README.md"
    )

    assert check_change(changed, []) == []


def test_check_change__code_without_fragment__is_a_problem() -> None:
    problems = check_change(_changed("src/footystreams/sim/engine.py"), [])

    assert [problem.rule for problem in problems] == ["fragment-required"]


def test_check_change__deleting_code_without_fragment__is_a_problem() -> None:
    problems = check_change(_changed("src/footystreams/sim/old.py", status="D"), [])

    assert [problem.rule for problem in problems] == ["fragment-required"]


def test_check_change__code_with_fragment__is_fine() -> None:
    assert check_change(_changed("src/a.py"), [_fragment()]) == []


def test_check_change__golden_files_need_a_sim_version_impact() -> None:
    changed = _changed("src/a.py", "tests/golden/digests.json")

    assert [p.rule for p in check_change(changed, [_fragment()])] == ["sim-version-impact"]
    assert check_change(changed, [_fragment(sim=Impact.MINOR)]) == []


def test_check_change__schemas_need_a_schema_version_impact() -> None:
    changed = _changed("schemas/events.schema.json")

    assert [p.rule for p in check_change(changed, [_fragment()])] == ["schema-version-impact"]
    assert check_change(changed, [_fragment(schema=Impact.PATCH)]) == []


def test_render_changelog__no_fragments__says_so() -> None:
    assert "_No unreleased changes._" in render_changelog([])


def test_render_changelog__groups_by_type_newest_first_with_notes() -> None:
    text = render_changelog(
        [
            _fragment("0001"),
            _fragment("0002", ChangeType.FIXED, sim=Impact.PATCH),
            _fragment("0003"),
        ]
    )

    assert text.index("### Added") < text.index("### Fixed")
    assert text.index("**0003**") < text.index("**0001**")
    assert "- **0002** Summary 0002 *(M4; scope: sim; sim version patch)*" in text
    assert text.endswith("\n")


def test_render_changelog__breaking_and_migration_are_called_out() -> None:
    text = render_changelog([_fragment(disruptive=True)])

    assert "**BREAKING** (migration needed) Summary 0001" in text


def test_render_changelog__is_deterministic_regardless_of_input_order() -> None:
    fragments = [_fragment("0001"), _fragment("0002"), _fragment("0003", ChangeType.DOCS)]

    assert render_changelog(fragments) == render_changelog(list(reversed(fragments)))
