"""Twenty seasons of a four-club league: the world stays in band (docs/design/07 section 8)."""

from __future__ import annotations

import datetime as dt

import pytest

from footystreams.domain.transfer import OUTSIDE_WORLD
from footystreams.league.health import Health, health
from footystreams.verify import SquadRules, check_development, check_squads
from tests.factories.league_config import make_development_config
from tests.factories.league_run import make_multi_runner
from tests.helpers.assertions import assert_no_violations

SEASONS = 20
SQUAD = make_development_config().squad
RULES = SquadRules(SQUAD.min_senior, SQUAD.max_senior, SQUAD.min_goalkeepers)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


@pytest.mark.slow
@pytest.mark.statistical
@pytest.mark.timeout(1500)
def test_twenty_seasons__ability_age_squads_and_retirements_stay_in_band() -> None:
    runner, factory = make_multi_runner(2, 4)
    states: list[Health] = []
    retirement_rates: list[float] = []
    for _ in range(SEASONS):
        results = runner.run_seasons(1)
        with factory() as uow:
            players = uow.players.all()
            clubs = [c for c in uow.clubs.all() if c.id != OUTSIDE_WORLD]
            today = uow.meta.require("current_date").value
            day = dt.date.fromisoformat(today)
            states.append(health(players, clubs, day))
            assert_no_violations(check_squads(players, [c.id for c in clubs], RULES))
            assert_no_violations(check_development(players))
            natural = uow.world_events.find(
                {"kind": "retirement", "date": day - dt.timedelta(days=1)}
            )
        assert len(results[0].table) == 4
        retirement_rates.append(len(natural) / states[-1].seniors)
    ability = [s.mean_ability for s in states]
    assert abs(_mean(ability[-4:]) - _mean(ability[:4])) <= 1.5
    assert all(24.0 <= s.mean_age <= 28.5 for s in states)
    assert 0.03 <= _mean(retirement_rates) <= 0.10
