"""M09 (docs/design/10 section 9) as an engine-level test: events carry no fitness data."""

from footystreams.domain.types import PlayerId
from footystreams.sim import SimConfig, default_tables, merge_config
from footystreams.sim.engine import MatchEngine
from tests.factories.sim_teams import make_demo_setup

EVERYTHING_ON = {
    "fatigue": {"enabled": True},
    "injury": {"enabled": True, "foul_contact": 0.1, "non_contact_per_match": 2.0},
    "manager": {"enabled": True},
}


def _falls_within_a_period(seed: int) -> list[str]:
    config = merge_config(SimConfig(), EVERYTHING_ON)
    engine = MatchEngine(make_demo_setup(), seed, config, default_tables())
    state = engine.state
    last: dict[PlayerId, float] = {}
    period = state.period
    falls: list[str] = []
    for event in engine.run():
        if state.period != period:
            period, last = state.period, {}
        for team in (state.home, state.away):
            for player in team.players:
                if player.exhaustion < last.get(player.player_id, 0.0):
                    falls.append(f"{player.player_id} after {event.id}")
                last[player.player_id] = player.exhaustion
    return falls


def test_exhaustion__never_falls_within_a_half() -> None:
    assert _falls_within_a_period(31) == []


def test_exhaustion__players_do_tire_over_a_match() -> None:
    config = merge_config(SimConfig(), EVERYTHING_ON)
    engine = MatchEngine(make_demo_setup(), 32, config, default_tables())
    for _ in engine.run():
        pass
    assert max(player.exhaustion for player in engine.state.home.players) > 0.1
