from __future__ import annotations

import asyncio
import datetime as dt
from pathlib import Path

import pytest
from pydantic import ValidationError

from footystreams.runtime.clock import ScaledClock, SystemClock, VirtualClock
from footystreams.runtime.config import EngineConfig, PaceKind, parse_pace


def test_virtual_clock__sleeping_jumps_to_the_moment_and_never_goes_back() -> None:
    clock = VirtualClock()

    asyncio.run(clock.sleep_until(90.0))
    asyncio.run(clock.sleep_until(30.0))

    assert clock.now() == 90.0


def test_virtual_clock__can_be_advanced_by_hand_but_not_backwards() -> None:
    clock = VirtualClock()

    clock.advance(12.5)

    assert clock.now() == 12.5
    with pytest.raises(ValueError, match="backwards"):
        clock.advance(-1.0)


def test_system_clock__is_monotonic_and_waiting_for_the_past_returns_at_once() -> None:
    clock = SystemClock()
    first = clock.now()

    asyncio.run(clock.sleep_until(first - 100.0))

    assert clock.now() >= first


def test_scaled_clock__runs_the_timeline_faster_than_the_wall() -> None:
    clock = ScaledClock(speed=2000.0)

    asyncio.run(clock.sleep_until(10.0))  # ten channel seconds in five wall milliseconds

    assert clock.now() >= 10.0


def test_scaled_clock__needs_a_positive_speed() -> None:
    with pytest.raises(ValueError, match="positive"):
        ScaledClock(speed=0.0)


@pytest.mark.parametrize(
    ("text", "kind", "speed"),
    [
        ("realtime", PaceKind.REALTIME, 1.0),
        ("instant", PaceKind.INSTANT, 1.0),
        ("scaled:200", PaceKind.SCALED, 200.0),
        ("scaled:0.5", PaceKind.SCALED, 0.5),
    ],
)
def test_parse_pace__reads_the_three_modes(text: str, kind: PaceKind, speed: float) -> None:
    pace = parse_pace(text)

    assert (pace.kind, pace.speed) == (kind, speed)


@pytest.mark.parametrize("text", ["fast", "scaled:", "scaled:x", "scaled:0", "scaled:-3", ""])
def test_parse_pace__anything_else_is_a_value_error(text: str) -> None:
    with pytest.raises(ValueError):  # noqa: PT011 - pydantic's ValidationError is a ValueError
        parse_pace(text)


def test_pace__builds_the_matching_clock() -> None:
    assert isinstance(parse_pace("instant").clock(), VirtualClock)
    assert isinstance(parse_pace("realtime").clock(), SystemClock)
    assert isinstance(parse_pace("scaled:5").clock(), ScaledClock)


def test_engine_config__defaults_are_valid_and_files_sit_beside_the_database(
    tmp_path: Path,
) -> None:
    config = EngineConfig(db_path=tmp_path / "league.sqlite")

    assert config.pace.kind is PaceKind.REALTIME
    assert config.lock_path.name == "league.sqlite.lock"
    assert config.health_path.name == "league.sqlite.health.json"


def test_engine_config__a_finite_run_names_one_end(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="not both"):
        EngineConfig(db_path=tmp_path / "x", max_seasons=1, until_date=dt.date(2032, 1, 1))


def test_engine_config__is_frozen_and_rejects_unknown_settings(tmp_path: Path) -> None:
    config = EngineConfig(db_path=tmp_path / "x")

    with pytest.raises(ValidationError):
        config.safe_mode = True  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EngineConfig(db_path=tmp_path / "x", turbo=True)  # type: ignore[call-arg]
