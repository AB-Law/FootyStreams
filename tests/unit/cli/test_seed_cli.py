from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from footystreams.cli import seed as seed_cli
from footystreams.cli.seed import EXIT_OK, EXIT_USAGE, EXIT_VIOLATIONS, main
from footystreams.seed.world_io import build_manifest, read_manifest, write_world
from tests.factories.world import make_world


@pytest.fixture(autouse=True)
def _cached_generation(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """Generation takes seconds and is covered elsewhere; the CLI tests reuse the cached world.

    The subprocess test is deliberately left alone: it runs the real thing end to end.
    """
    if "separate_process" in request.node.name:
        return
    monkeypatch.setattr(seed_cli, "generate_world", lambda seed, config, tables: make_world(seed))


def test_seed__writes_a_world_and_reports_the_hash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--seed", "1", "--out", str(tmp_path / "w")]) == EXIT_OK
    output = capsys.readouterr().out
    assert "coherence checks: PASS" in output
    assert "wrote" in output
    assert read_manifest(tmp_path / "w").content_sha256 in output


def test_seed__validate_only_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["--seed", "1", "--validate", "--out", str(tmp_path / "w")])
    assert code == EXIT_OK
    assert not (tmp_path / "w").exists()
    assert "PASS" in capsys.readouterr().out


def test_seed__validate_an_existing_world_directory(tmp_path: Path) -> None:
    write_world(make_world(1), tmp_path)
    assert main(["--validate", "--world", str(tmp_path)]) == EXIT_OK


def test_seed__validate_world_with_violations__exit_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    world = make_world(1)
    broken_club = world.clubs[0].model_copy(update={"manager_id": "mgr_unknown"})
    import dataclasses  # noqa: PLC0415

    write_world(dataclasses.replace(world, clubs=(broken_club, *world.clubs[1:])), tmp_path)
    assert main(["--validate", "--world", str(tmp_path)]) == EXIT_VIOLATIONS
    assert "[W01]" in capsys.readouterr().out


def test_seed__bad_club_count__exit_two_with_a_one_line_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--clubs", "99"]) == EXIT_USAGE
    error = capsys.readouterr().err
    assert error.startswith("seed: error:")
    assert "Traceback" not in error


def test_seed__missing_world_directory__exit_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--validate", "--world", str(tmp_path / "nope")]) == EXIT_USAGE
    assert "seed: error:" in capsys.readouterr().err


def test_seed__separate_process_with_random_hash_seed__same_content_hash(tmp_path: Path) -> None:
    environment = {**os.environ, "PYTHONHASHSEED": "random"}
    result = subprocess.run(  # noqa: S603 - fixed arguments, our own module
        [
            sys.executable,
            "-m",
            "footystreams.cli.seed",
            "--seed",
            "1",
            "--out",
            str(tmp_path / "w"),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
    assert read_manifest(tmp_path / "w") == build_manifest(make_world(1))
