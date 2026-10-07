from __future__ import annotations

import datetime as dt

from footystreams.league.health import health
from tests.factories.world import make_world

WORLD = make_world(1)
TODAY = WORLD.created_in_world


def test_health__counts_seniors_youth_and_free_agents_and_averages_ability_and_age() -> None:
    state = health(WORLD.players, WORLD.clubs, TODAY)
    assert state.seniors == 200
    assert state.youth == 64
    assert state.free_agents == 30
    assert 55 < state.mean_ability < 70
    assert 24 < state.mean_age < 29
    assert state.clubs_in_debt == 0


def test_health__an_overdrawn_club_is_counted() -> None:
    club = WORLD.clubs[0]
    broke = club.model_copy(
        update={
            "finances": club.finances.model_copy(
                update={"balance": -club.finances.credit_limit - 1}
            )
        }
    )
    assert health(WORLD.players, [broke, *WORLD.clubs[1:]], TODAY).clubs_in_debt == 1


def test_health__no_players_is_not_a_division_by_zero() -> None:
    assert health([], WORLD.clubs, dt.date(2031, 7, 1)).mean_ability == 0.0
