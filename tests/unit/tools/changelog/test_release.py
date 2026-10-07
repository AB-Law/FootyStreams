import json
from datetime import date
from pathlib import Path

import pytest

from footystreams.tools.changelog.cli import main
from footystreams.tools.changelog.fragment import Impact
from footystreams.tools.changelog.release import strongest_impact
from footystreams.tools.changelog.store import FragmentStore

NEW = ["new", "--type", "added", "--scope", "sim", "--milestone", "M4", "--date", "2026-10-07"]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    main([*NEW, "Add the pass resolver", "--sim-impact", "minor"], root=tmp_path)
    breaking = ["--breaking", "--migration", "--schema-impact", "major"]
    changed = ["new", "--type", "changed", "--scope", "events", "--milestone", "M4"]
    main([*changed, "Rename a field", *breaking, "--date", "2026-10-08"], root=tmp_path)
    return tmp_path


def test_release__moves_fragments_and_writes_notes(root: Path) -> None:
    exit_code = main(["release", "0.1.0", "--date", "2026-11-01"], root=root)

    store = FragmentStore(root / "changes")
    assert exit_code == 0
    assert store.unreleased() == []
    assert [f.id for f in store.releases()[0].fragments] == ["0001", "0002"]
    assert (root / "release-notes" / "v0.1.0.md").exists()


def test_release__json_notes_are_structured_and_report_the_strongest_impacts(root: Path) -> None:
    main(["release", "0.1.0", "--date", "2026-11-01"], root=root)

    notes = json.loads((root / "release-notes" / "v0.1.0.json").read_text(encoding="utf-8"))

    assert (notes["version"], notes["date"]) == ("0.1.0", "2026-11-01")
    assert (notes["sim_version_impact"], notes["schema_version_impact"]) == ("minor", "major")
    assert [change["id"] for change in notes["changes"]] == ["0001", "0002"]


def test_release__markdown_notes_call_out_breaking_and_migration(root: Path) -> None:
    main(["release", "0.1.0", "--date", "2026-11-01"], root=root)

    text = (root / "release-notes" / "v0.1.0.md").read_text(encoding="utf-8")

    assert text.startswith("# Release v0.1.0 (2026-11-01)")
    assert "## Breaking changes\n- **0002** Rename a field" in text
    assert "## Migration steps required" in text
    assert "`SIM_VERSION`): **minor**" in text


def test_release__changelog_lists_the_release_below_unreleased(root: Path) -> None:
    main(["release", "0.1.0", "--date", "2026-11-01"], root=root)
    main([*NEW, "Add the shot model"], root=root)
    main(["build"], root=root)

    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")

    assert text.index("## [Unreleased]") < text.index("## [0.1.0] - 2026-11-01")
    assert text.index("**0003** Add the shot model") < text.index("## [0.1.0]")
    assert main(["build", "--check"], root=root) == 0


def test_release__new_fragment_ids_continue_after_a_release(root: Path) -> None:
    main(["release", "0.1.0", "--date", "2026-11-01"], root=root)

    assert FragmentStore(root / "changes").next_id() == "0003"


@pytest.mark.parametrize("version", ["1.0", "v1.0.0", "one"])
def test_release__invalid_version__exits_2(root: Path, version: str) -> None:
    assert main(["release", version], root=root) == 2
    assert len(FragmentStore(root / "changes").unreleased()) == 2


def test_release__same_version_twice_or_nothing_to_release__exits_2(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["release", "0.1.0"], root=root) == 0

    assert main(["release", "0.2.0"], root=root) == 2  # nothing left to release
    assert "no unreleased fragments" in capsys.readouterr().err


def test_releases__are_ordered_newest_version_first(root: Path) -> None:
    main(["release", "0.9.0", "--date", "2026-11-01"], root=root)
    main([*NEW, "Another"], root=root)
    main(["release", "0.10.0", "--date", "2026-12-01"], root=root)

    versions = [release.version for release in FragmentStore(root / "changes").releases()]

    assert versions == ["0.10.0", "0.9.0"]  # numeric, not alphabetical, ordering


def test_strongest_impact__orders_none_patch_minor_major() -> None:
    assert strongest_impact([]) is Impact.NONE
    assert strongest_impact([Impact.PATCH, Impact.MAJOR, Impact.MINOR]) is Impact.MAJOR
    assert strongest_impact([Impact.NONE, Impact.PATCH]) is Impact.PATCH


def test_release__date_defaults_to_today(root: Path) -> None:
    main(["release", "0.1.0"], root=root)

    assert FragmentStore(root / "changes").releases()[0].date == date.today()
