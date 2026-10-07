from __future__ import annotations

import datetime as dt

from footystreams.domain.rng import WorldRng
from footystreams.domain.staff import StaffRole
from footystreams.league.development import GROUPS
from footystreams.league.stages import TrainingStage
from footystreams.league.training import training_conditions
from tests.factories.league_db import make_league_db
from tests.factories.league_inputs import make_league_tables
from tests.factories.world import make_world

WORLD = make_world(1)
CONFIG = make_league_tables().development.progression
CLUB = WORLD.clubs[0]
STAFF = [s for s in WORLD.staff if s.club_id == CLUB.id]


def test_training_conditions__quality_is_between_zero_and_one_for_every_group() -> None:
    conditions = training_conditions(CLUB, STAFF, 0.8, CONFIG)
    assert set(conditions.training) == set(GROUPS)
    assert all(0.0 <= q <= 1.0 for q in conditions.training.values())
    assert conditions.playing_time == 0.8


def test_training_conditions__better_facilities__train_better() -> None:
    poor = CLUB.model_copy(
        update={"facilities": CLUB.facilities.model_copy(update={"training": 10})}
    )
    rich = CLUB.model_copy(
        update={"facilities": CLUB.facilities.model_copy(update={"training": 95})}
    )
    assert (
        training_conditions(rich, STAFF, 0.5, CONFIG).training["technical"]
        > training_conditions(poor, STAFF, 0.5, CONFIG).training["technical"]
    )


def test_training_conditions__better_fitness_coach__trains_physical_better() -> None:
    coach = next(s for s in STAFF if s.role is StaffRole.FITNESS_COACH)
    sharp = coach.model_copy(
        update={"attrs": coach.attrs.model_copy(update={"coaching_physical": 95})}
    )
    dull = coach.model_copy(
        update={"attrs": coach.attrs.model_copy(update={"coaching_physical": 5})}
    )
    others = [s for s in STAFF if s.id != coach.id]
    assert (
        training_conditions(CLUB, [sharp, *others], 0.5, CONFIG).training["physical"]
        > training_conditions(CLUB, [dull, *others], 0.5, CONFIG).training["physical"]
    )


def test_training_conditions__free_agent_and_no_staff__uses_the_neutral_floor() -> None:
    conditions = training_conditions(None, [], 0.5, CONFIG)
    expected = (1 - CONFIG.facility_weight) * 0.5
    assert all(abs(q - expected) < 1e-9 for q in conditions.training.values())


def test_training_stage__only_runs_on_pay_day_and_writes_only_changed_players() -> None:

    tables = make_league_tables()
    factory = make_league_db()
    stage = TrainingStage(tables)
    monday = dt.date(2031, 8, 18)
    with factory() as uow:
        assert stage.run(uow, monday + dt.timedelta(days=1), WorldRng(1)).is_empty()
        delta = stage.run(uow, monday, WorldRng(1))
        everyone = len(uow.players.all())
    assert 0 < len(delta.players) < everyone
    for player in delta.players:
        assert player.ability_current <= player.ability_potential
        assert player.development_log[-1].cause == "training"
