from __future__ import annotations

from pathlib import Path

import pytest

from footystreams.cli import league as league_cli
from footystreams.cli.league import EXIT_OK, EXIT_USAGE, main
from footystreams.seed.world_io import write_world
from tests.factories.world import make_world


@pytest.fixture(autouse=True)
def _cached_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Generation is covered by the seed tests; the CLI reuses the cached world."""
    monkeypatch.setattr(
        league_cli, "generate_world", lambda seed, config, tables: make_world(seed, config.clubs)
    )


def test_league__plays_a_season_and_prints_the_table_and_the_money(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--seed", "2", "--clubs", "4"]) == EXIT_OK
    output = capsys.readouterr().out
    assert "2031/32: 12 matches played" in output
    assert "Pts" in output
    assert "Balance" in output


def test_league__matchday_option__stops_after_that_matchday(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--seed", "2", "--clubs", "4", "--matchday", "2"]) == EXIT_OK
    output = capsys.readouterr().out
    assert "4 matches played" in output


def test_league__world_directory__is_used_instead_of_the_seed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_world(make_world(2, 4), tmp_path)
    assert main(["--world", str(tmp_path), "--matchday", "1"]) == EXIT_OK
    assert "2 matches played" in capsys.readouterr().out


def test_league__missing_world_directory__is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--world", str(tmp_path / "nowhere")]) == EXIT_USAGE
    assert "league: error" in capsys.readouterr().err


@pytest.mark.slow
@pytest.mark.timeout(240)
def test_league__database__resumes_where_it_stopped_and_ends_where_a_straight_run_does(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database = str(tmp_path / "league.db")
    assert main(["--seed", "2", "--clubs", "4", "--db", database, "--matchday", "3"]) == EXIT_OK
    assert "6 matches played" in capsys.readouterr().out
    assert main(["--seed", "2", "--clubs", "4", "--db", database]) == EXIT_OK
    resumed = capsys.readouterr().out
    assert main(["--seed", "2", "--clubs", "4"]) == EXIT_OK
    straight = capsys.readouterr().out
    assert resumed.split("\n", 1)[1].split("\n\n")[0] == straight.split("\n", 1)[1].split("\n\n")[0]


def test_league__seasons_option__plays_that_many_seasons_with_the_off_season_between(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--seed", "2", "--clubs", "4", "--seasons", "2"]) == EXIT_OK
    output = capsys.readouterr().out
    assert "2031/32: 12 matches played" in output
    assert "2032/33: 12 matches played" in output
    assert "now 2033-06-02" in output
