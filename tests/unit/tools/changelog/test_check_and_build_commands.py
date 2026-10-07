from pathlib import Path

import pytest

from footystreams.tools import git
from footystreams.tools.changelog.cli import main

NEW = ["new", "--type", "added", "--scope", "sim", "--milestone", "M4", "--date", "2026-10-07"]


def test_check__no_changes__passes(repo: Path) -> None:
    assert main(["check", "--base", "main"], root=repo) == 0


def test_check__code_change_without_fragment__fails_and_explains(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")

    exit_code = main(["check", "--base", "main"], root=repo)

    assert exit_code == 1
    assert "[fragment-required]" in capsys.readouterr().err


def test_check__code_change_with_new_fragment__passes_even_when_uncommitted(repo: Path) -> None:
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    main([*NEW, "Add a"], root=repo)

    assert main(["check", "--base", "main"], root=repo) == 0


def test_check__malformed_fragment__exits_2(repo: Path) -> None:
    unreleased = repo / "changes" / "unreleased"
    unreleased.mkdir(parents=True)
    (unreleased / "0001-bad.md").write_text("not a fragment", encoding="utf-8")

    assert main(["check", "--base", "main"], root=repo) == 2


def test_check__unknown_base__exits_2(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", "--base", "nope"], root=repo) == 2
    assert "none of" in capsys.readouterr().err


def test_resolve_base__falls_back_to_main_when_there_is_no_origin(repo: Path) -> None:
    assert git.resolve_base(repo) == "main"


def test_build__writes_changelog_and_check_detects_staleness(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main([*NEW, "Add a"], root=repo)
    assert main(["build", "--check"], root=repo) == 1  # no CHANGELOG.md yet

    assert main(["build"], root=repo) == 0
    assert "**0001** Add a" in (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    assert main(["build", "--check"], root=repo) == 0

    main([*NEW, "Add b"], root=repo)
    assert main(["build", "--check"], root=repo) == 1
    assert "stale" in capsys.readouterr().err
