"""``uv run sim --home A --away B --world DIR``: a friendly between two clubs of a world."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from footystreams.cli.sim import main
from footystreams.seed.world_io import write_world
from tests.factories.world import make_world

pytestmark = pytest.mark.timeout(120)


@pytest.fixture(scope="module")
def world_directory(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("world")
    write_world(make_world(2, 4), directory)
    return directory


def _club_names(world_directory: Path) -> list[str]:
    clubs = json.loads((world_directory / "clubs.json").read_text(encoding="utf-8"))
    return [club["short_code"] for club in clubs][:2]


def test_main__two_clubs_of_a_world__plays_their_friendly(
    world_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    home, away = _club_names(world_directory)

    code = main(["--home", home, "--away", away, "--world", str(world_directory), "--seed", "3"])

    assert code == 0
    output = capsys.readouterr().out
    assert "Kick-off" in output
    assert home in output
    assert away in output


def test_main__a_world_friendly_is_deterministic_per_seed(
    world_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    home, away = _club_names(world_directory)
    arguments = ["--home", home, "--away", away, "--world", str(world_directory), "--seed", "5"]
    main([*arguments, "--format", "ndjson"])
    first = capsys.readouterr().out
    main([*arguments, "--format", "ndjson"])

    assert first == capsys.readouterr().out


def test_main__unknown_club__is_a_usage_error(
    world_directory: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["--home", "NOP", "--away", "ZZZ", "--world", str(world_directory)])

    assert code == 2
    assert "error" in capsys.readouterr().err


def test_main__clubs_without_a_world__explains_what_is_missing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--home", "AAA", "--away", "BBB"]) == 2
    assert "--world" in capsys.readouterr().err
