from datetime import date
from pathlib import Path

import pytest

from footystreams.tools.changelog.cli import main
from footystreams.tools.changelog.fragment import parse_fragment
from footystreams.tools.changelog.store import FragmentStore

NEW = ["new", "--type", "added", "--scope", "sim", "--milestone", "M4", "--date", "2026-10-07"]


def test_new__empty_directory__creates_fragment_0001(tmp_path: Path) -> None:
    exit_code = main([*NEW, "Add the pass resolver"], root=tmp_path)

    created = tmp_path / "changes" / "unreleased" / "0001-add-the-pass-resolver.md"
    assert exit_code == 0
    assert (
        parse_fragment(created.read_text(encoding="utf-8"), "x").summary == "Add the pass resolver"
    )


def test_new__existing_fragments__uses_next_id_across_unreleased_and_released(
    tmp_path: Path,
) -> None:
    main([*NEW, "First"], root=tmp_path)
    released = tmp_path / "changes" / "released" / "0.1.0"
    released.mkdir(parents=True)
    (tmp_path / "changes" / "unreleased" / "0001-first.md").rename(released / "0007-old.md")
    (released / "0007-old.md").write_text(
        (released / "0007-old.md").read_text(encoding="utf-8").replace("id: 0001", "id: 0007"),
        encoding="utf-8",
    )

    main([*NEW, "Second"], root=tmp_path)

    assert FragmentStore(tmp_path / "changes").unreleased()[0].id == "0008"


def test_new__summary_with_quotes_and_colons__is_preserved(tmp_path: Path) -> None:
    summary = "Fix: handle the 'late' winner # case"

    main([*NEW, summary], root=tmp_path)

    assert FragmentStore(tmp_path / "changes").unreleased()[0].summary == summary


def test_new__invalid_summary__reports_error_and_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main([*NEW, "   "], root=tmp_path)

    assert exit_code == 2
    assert "summary" in capsys.readouterr().err


def test_new__flags__are_recorded(tmp_path: Path) -> None:
    main(
        [*NEW, "Break it", "--breaking", "--migration", "--config-impact", "--sim-impact", "major"],
        root=tmp_path,
    )

    fragment = FragmentStore(tmp_path / "changes").unreleased()[0]
    assert (fragment.breaking, fragment.migration, fragment.config_impact) == (True, True, True)
    assert fragment.sim_version_impact == "major"
    assert fragment.date == date(2026, 10, 7)


def test_store_unreleased__ignores_non_fragment_files(tmp_path: Path) -> None:
    (tmp_path / "changes" / "unreleased").mkdir(parents=True)
    (tmp_path / "changes" / "unreleased" / "README.md").write_text(
        "not a fragment", encoding="utf-8"
    )

    assert FragmentStore(tmp_path / "changes").unreleased() == []
    assert FragmentStore(tmp_path / "changes").next_id() == "0001"
