from __future__ import annotations

import datetime as dt

from footystreams.domain.injury import Injury, InjurySeverity
from footystreams.domain.player import PlayerStatus
from footystreams.league.clock import WorldClock, read_date, write_date
from footystreams.league.recovery import decay_sharpness, recover
from tests.factories.league_config import make_league_config
from tests.factories.league_db import make_league_db
from tests.factories.world import make_world

CONFIG = make_league_config().recovery
TODAY = dt.date(2031, 9, 1)
PLAYER = make_world(1).players[0]


def test_recover__tired_player__loses_fatigue_gains_fitness_and_settles_morale() -> None:
    tired = PLAYER.model_copy(update={"fatigue": 0.35, "fitness": 0.9, "morale": 0.62})
    rested = recover(tired, TODAY, CONFIG)
    assert rested.fatigue == 0.25
    assert rested.fitness > 0.9
    assert rested.morale < 0.62


def test_recover__morale_below_neutral__rises_towards_it_without_overshooting() -> None:
    low = PLAYER.model_copy(update={"morale": 0.495, "fatigue": 0.0, "fitness": 1.0})
    assert recover(low, TODAY, CONFIG).morale == 0.5


def test_recover__nothing_to_recover__returns_the_same_object() -> None:
    settled = PLAYER.model_copy(update={"fatigue": 0.0, "fitness": 1.0, "morale": 0.5})
    assert recover(settled, TODAY, CONFIG) is settled


def test_recover__injury_on_the_return_date__heals_and_enters_the_history() -> None:
    injury = Injury(
        type="hamstring_strain",
        body_part="hamstring",
        severity=InjurySeverity.MINOR,
        started_on=TODAY - dt.timedelta(days=10),
        expected_return_on=TODAY,
    )
    healed = recover(PLAYER.model_copy(update={"current_injury": injury}), TODAY, CONFIG)
    assert healed.current_injury is None
    assert healed.injury_history[-1].returned_on == TODAY
    assert healed.injury_history[-1].type == "hamstring_strain"


def test_recover__injury_still_running__keeps_the_player_hurt_and_his_fitness_flat() -> None:
    injury = Injury(
        type="x",
        body_part="knee",
        severity=InjurySeverity.MODERATE,
        started_on=TODAY,
        expected_return_on=TODAY + dt.timedelta(days=9),
    )
    hurt = PLAYER.model_copy(update={"current_injury": injury, "fitness": 0.7})
    after = recover(hurt, TODAY, CONFIG)
    assert after.current_injury == injury
    assert after.fitness == 0.7


def test_recover__retired_player__is_untouched() -> None:
    retired = PLAYER.model_copy(update={"status": PlayerStatus.RETIRED, "fatigue": 0.5})
    assert recover(retired, TODAY, CONFIG) is retired
    assert decay_sharpness(retired, CONFIG) is retired


def test_decay_sharpness__lowers_it_by_the_weekly_step_but_not_below_the_floor() -> None:
    sharp = PLAYER.model_copy(update={"match_sharpness": 0.8})
    assert decay_sharpness(sharp, CONFIG).match_sharpness == round(
        0.8 - CONFIG.sharpness_decay_idle_week, 4
    )
    floor = PLAYER.model_copy(update={"match_sharpness": CONFIG.sharpness_floor})
    assert decay_sharpness(floor, CONFIG) is floor


def test_decay_sharpness__below_the_floor__is_left_alone() -> None:
    rusty = PLAYER.model_copy(update={"match_sharpness": 0.1})
    assert decay_sharpness(rusty, CONFIG) is rusty


def test_world_clock__reads_and_advances_the_stored_date() -> None:
    factory = make_league_db()
    clock = WorldClock(factory)
    start = clock.current_date()
    assert clock.advance_day() == start + dt.timedelta(days=1)
    assert clock.current_date() == start + dt.timedelta(days=1)


def test_write_date__persists_through_the_repositories() -> None:
    factory = make_league_db()
    with factory() as uow:
        write_date(uow, dt.date(2040, 1, 2))
        uow.commit()
    with factory() as uow:
        assert read_date(uow) == dt.date(2040, 1, 2)
