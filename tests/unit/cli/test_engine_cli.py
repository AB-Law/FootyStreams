from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from footystreams.cli.engine import EXIT_USAGE, build_parser, config_from, main
from footystreams.events.broadcast import EngineMarker, MarkerKind, from_line
from footystreams.runtime.config import EngineConfig, PaceKind
from footystreams.seed.world_io import write_world
from tests.factories.world import make_world

pytestmark = pytest.mark.timeout(240)


def _config(*extra: str) -> EngineConfig:
    return config_from(build_parser().parse_args(["--db", "x.sqlite", *extra]))


def test_config__defaults_are_the_channel_in_real_time_on_stdout() -> None:
    config = _config()

    assert config.pace.kind is PaceKind.REALTIME
    assert config.sinks == ("ndjson:stdout",)
    assert config.safe_mode is False


def test_config__every_option_reaches_the_engine_settings() -> None:
    config = _config(
        "--pace", "scaled:200", "--sink", "memory", "--sink", "ndjson:file:a.ndjson",
        "--until-date", "2031-09-01", "--buffer-matchdays", "3", "--cursor-every", "7",
        "--starve-grace-s", "4", "--safe-mode",
    )  # fmt: skip

    assert (config.pace.kind, config.pace.speed) == (PaceKind.SCALED, 200.0)
    assert config.sinks == ("memory", "ndjson:file:a.ndjson")
    assert config.until_date == dt.date(2031, 9, 1)
    assert (config.buffer_matchdays, config.cursor_every) == (3, 7)
    assert (config.starve_grace_s, config.safe_mode) == (4.0, True)


@pytest.mark.parametrize(
    "extra",
    [
        ["--pace", "warp"],
        ["--sink", "carrier-pigeon"],
        ["--max-seasons", "1", "--until-date", "2031-09-01"],
    ],
)
def test_main__bad_settings_are_a_usage_error(
    tmp_path: Path, extra: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["--db", str(tmp_path / "x.sqlite"), "--world", str(tmp_path / "none"), *extra])

    assert code == EXIT_USAGE
    assert "engine: error" in capsys.readouterr().err


def test_main__a_new_database_without_a_world_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["--db", str(tmp_path / "new.sqlite"), "--world", str(tmp_path / "nowhere")])

    assert code == EXIT_USAGE
    assert "engine: error" in capsys.readouterr().err


@pytest.mark.slow
def test_main__a_finite_instant_run_writes_the_broadcast_as_ndjson(tmp_path: Path) -> None:
    write_world(make_world(2, 4), tmp_path / "world")
    out = tmp_path / "broadcast.ndjson"

    code = main(
        [
            "--db", str(tmp_path / "league.sqlite"), "--world", str(tmp_path / "world"),
            "--pace", "instant", "--until-date", "2031-08-15", "--sink", f"ndjson:file:{out}",
            "--starve-grace-s", "60", "--log-level", "ERROR",
        ]
    )  # fmt: skip

    events = [from_line(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert code == 0
    first, last = events[0], events[-1]
    assert isinstance(first, EngineMarker)
    assert isinstance(last, EngineMarker)
    assert (first.marker, last.marker) == (MarkerKind.START, MarkerKind.STOP)
    assert {json.loads(line)["type"] for line in out.read_text(encoding="utf-8").splitlines()} >= {
        "segment_started",
        "kickoff",
        "match_summary",
    }
