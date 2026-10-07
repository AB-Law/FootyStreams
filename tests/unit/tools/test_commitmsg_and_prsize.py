from pathlib import Path

import pytest

from footystreams.tools.commitmsg import main as commit_msg_main
from footystreams.tools.commitmsg import problems_with
from footystreams.tools.prsize import (
    HARD_CAP_LINES,
    TARGET_LINES,
    Verdict,
    counted_lines,
    verdict_for,
)
from footystreams.tools.prsize import main as pr_size_main
from tests.unit.tools.conftest import git


@pytest.mark.parametrize(
    "message",
    [
        "feat(sim): add offside detection",
        "fix: handle an empty bench",
        "refactor(league)!: rename the ledger category",
        "chore(golden): regenerate digests\n\nBody explaining why.\n\nChangelog: 0042",
        "feat(sim): subject\n# a comment line git adds\n",
        "Merge pull request #7 from AB-Law/branch",
        "fixup! feat(sim): add offside detection",
    ],
)
def test_problems_with__valid_messages__are_accepted(message: str) -> None:
    assert problems_with(message) == []


@pytest.mark.parametrize(
    ("message", "fragment"),
    [
        ("added offside detection", "type(scope)"),
        ("Feat(sim): capitalised type", "type(scope)"),
        ("feat(Sim): capitalised scope", "type(scope)"),
        ("feat(sim):no space after colon", "type(scope)"),
        ("feat(sim): " + "x" * 70, "characters"),
        ("feat(sim): fine subject\nbody directly after", "blank line"),
        ("   \n# only comments", "empty"),
    ],
)
def test_problems_with__invalid_messages__explain_why(message: str, fragment: str) -> None:
    assert any(fragment in problem for problem in problems_with(message))


def test_commit_msg_main__reads_the_message_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good, bad = tmp_path / "good", tmp_path / "bad"
    good.write_text("feat(sim): add a thing\n", encoding="utf-8")
    bad.write_text("added a thing\n", encoding="utf-8")

    assert commit_msg_main([str(good)]) == 0
    assert commit_msg_main([str(bad)]) == 1
    assert "commit message:" in capsys.readouterr().err
    assert commit_msg_main([]) == 2


def test_counted_lines__sums_added_and_deleted_and_skips_generated_and_binary() -> None:
    numstat = "\n".join(
        [
            "10\t5\tsrc/a.py",
            "3\t0\ttests/test_a.py",
            "900\t100\tuv.lock",
            "400\t0\tschemas/events.schema.json",
            "50\t50\ttests/golden/digests.json",
            "-\t-\tdocs/logo.png",
        ]
    )

    assert counted_lines(numstat) == 18


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (0, Verdict.OK),
        (TARGET_LINES, Verdict.OK),
        (TARGET_LINES + 1, Verdict.OVER_TARGET),
        (HARD_CAP_LINES, Verdict.OVER_TARGET),
        (HARD_CAP_LINES + 1, Verdict.OVER_CAP),
    ],
)
def test_verdict_for__boundaries(lines: int, expected: Verdict) -> None:
    assert verdict_for(lines) is expected


def _commit_lines(repo: Path, count: int) -> None:
    (repo / "big.py").write_text("x = 1\n" * count, encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "feat: add a big file")


def test_pr_size_main__small_pr__exits_zero(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _commit_lines(repo, 10)

    assert pr_size_main(["--base", "main"], root=repo) == 0
    assert "10 changed lines" in capsys.readouterr().out


def test_pr_size_main__over_the_cap__fails_unless_a_human_allowed_it(repo: Path) -> None:
    _commit_lines(repo, HARD_CAP_LINES + 1)

    assert pr_size_main(["--base", "main"], root=repo) == 1
    assert pr_size_main(["--base", "main", "--allow-large"], root=repo) == 0


def test_pr_size_main__unknown_base__exits_two(repo: Path) -> None:
    assert pr_size_main(["--base", "nope"], root=repo) == 2
