from __future__ import annotations

from pathlib import Path

import pytest

from footystreams.cli.balance import EXIT_OFF_TARGET, EXIT_USAGE, main
from footystreams.seed.world_io import write_world
from tests.factories.world import make_world

pytestmark = pytest.mark.timeout(240)


@pytest.fixture(scope="module")
def world_directory(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("balance_world")
    write_world(make_world(2, 4), directory)
    return directory


def _run(world: Path, *extra: str) -> list[str]:
    return ["--world", str(world), "--matches", "6", "--workers", "1", *extra]


def test_balance__prints_the_targets_table_and_summary(
    world_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(_run(world_directory))

    output = capsys.readouterr().out
    assert "profile realistic, 6 matches" in output
    assert "goals_per_match" in output
    assert "PASS, loss" in output
    assert code in (0, EXIT_OFF_TARGET)


def test_balance__failures_flag_repeats_only_the_misses(
    world_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(_run(world_directory, "--failures"))

    table, _, misses = capsys.readouterr().out.partition("\n\n")
    assert misses
    assert all(line.split()[-1] != "PASS" for line in misses.splitlines())
    assert len(misses.splitlines()) < len(table.splitlines())


@pytest.mark.slow
def test_balance__set_changes_the_run(
    world_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(_run(world_directory))
    base = capsys.readouterr().out
    main(_run(world_directory, "--set", "home_advantage_scale=0"))

    assert capsys.readouterr().out != base


@pytest.mark.slow
def test_balance__a_config_file_is_the_same_as_the_equivalent_set(
    world_directory: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "tuned.yaml"
    config.write_text("home_advantage_scale: 0\n", encoding="utf-8")
    main(_run(world_directory, "--set", "home_advantage_scale=0"))
    via_set = capsys.readouterr().out
    main(_run(world_directory, "--config", str(config)))

    assert capsys.readouterr().out == via_set


@pytest.mark.parametrize(
    "extra",
    [["--profile", "utopia"], ["--set", "shot.nope=1"], ["--set", "shot"]],
)
def test_balance__bad_input_is_a_usage_error(
    world_directory: Path, extra: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_run(world_directory, *extra)) == EXIT_USAGE
    assert "balance: error" in capsys.readouterr().err


def test_balance__a_missing_world_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_run(tmp_path / "nowhere")) == EXIT_USAGE
    assert "balance: error" in capsys.readouterr().err


def test_balance_sensitivity__prints_a_matrix_and_the_strongest_knobs(
    world_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "sensitivity",
            *_run(world_directory),
            "--knobs",
            "shot.xg_cap",
            "--metrics",
            "goals_per_match",
        ]
    )

    output = capsys.readouterr().out
    assert code == 0
    assert "shot.xg_cap" in output
    assert "moves goals_per_match: shot.xg_cap" in output


@pytest.mark.parametrize(
    "extra",
    [[], ["--knobs", "shot.nope"], ["--knobs", "shot.xg_cap", "--metrics", "not_a_metric"]],
)
def test_balance_sensitivity__bad_input_is_a_usage_error(
    world_directory: Path, extra: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["sensitivity", *_run(world_directory), *extra]) == EXIT_USAGE
    assert "balance: error" in capsys.readouterr().err
