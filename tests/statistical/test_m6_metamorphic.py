"""M6 metamorphic sweeps: changing one condition moves the outcome the way football says."""

from collections.abc import Iterable

import pytest

from footystreams.domain.weather import Weather, WeatherCondition
from footystreams.events.clock import match_elapsed_s
from footystreams.events.open_play import PassEvent
from footystreams.events.types import MatchEvent
from footystreams.sim import SimConfig, default_tables, merge_config, run_match
from footystreams.sim.engine import MatchEngine
from tests.factories.sim_teams import make_demo_setup

pytestmark = [pytest.mark.slow, pytest.mark.statistical, pytest.mark.timeout(1800)]

TABLES = default_tables()
LATE_S = 3600
LONG_PASS_M = 25.0


def _weather(**changes: object) -> Weather:
    values: dict[str, object] = {
        "condition": WeatherCondition.CLEAR,
        "temperature_c": 15.0,
        "humidity": 0.5,
        "wind_speed_mps": 2.0,
        "wind_direction_deg": 90,
        "rain_mm_per_h": 0.0,
        "pitch_wetness": 0.0,
        "visibility": 1.0,
    }
    values.update(changes)
    return Weather(**values)  # type: ignore[arg-type]


def _logs(matches: int, config: SimConfig, base_seed: int) -> Iterable[tuple[MatchEvent, ...]]:
    setup = make_demo_setup()
    for index in range(matches):
        yield run_match(setup, base_seed + index, config, TABLES).events


def test_home_advantage__a_loud_home_crowd_lifts_the_home_goal_difference() -> None:
    def mean_goal_difference(scale: float) -> float:
        config = merge_config(SimConfig(), {"home_advantage_scale": scale})
        matches = 400
        total = 0
        for log in _logs(matches, config, 5000):
            final = log[-2].ctx
            total += final.score_home - final.score_away
        return total / matches

    assert mean_goal_difference(3.0) - mean_goal_difference(0.0) > 0.08


def test_weather__heavy_rain_makes_teams_play_fewer_long_balls() -> None:
    """Long balls are riskier on a soaked pitch, so the decision model picks fewer of them.

    Completion of the long balls that are still tried does not fall (the survivors are the
    well-placed ones), which is why the effect is measured on attempts.
    """

    def long_passes_a_match(weather: Weather) -> float:
        setup = make_demo_setup(weather=weather)
        matches, longs = 40, 0
        for index in range(matches):
            events = run_match(setup, 300 + index, SimConfig(), TABLES).events
            longs += sum(isinstance(e, PassEvent) and e.length_m >= LONG_PASS_M for e in events)
        return longs / matches

    rain = _weather(condition=WeatherCondition.HEAVY_RAIN, rain_mm_per_h=12.0, pitch_wetness=1.0)
    assert long_passes_a_match(rain) < 0.92 * long_passes_a_match(_weather())


def test_weather__heat_leaves_players_more_exhausted_at_the_end() -> None:
    def mean_exhaustion(weather: Weather) -> float:
        setup = make_demo_setup(weather=weather)
        values: list[float] = []
        for index in range(8):
            engine = MatchEngine(setup, 400 + index, SimConfig(), TABLES)
            for _ in engine.run():
                pass
            values.extend(p.exhaustion for p in engine.state.home.players[1:])
        return sum(values) / len(values)

    hot = _weather(temperature_c=35.0, humidity=0.9)
    assert mean_exhaustion(hot) > mean_exhaustion(_weather()) * 1.05


def test_manager__trailing_teams_shoot_more_than_leading_ones_after_sixty_minutes() -> None:
    trailing = leading = 0
    for log in _logs(150, SimConfig(), 9000):
        for event in log:
            level = event.ctx.score_home == event.ctx.score_away
            if event.type != "shot" or match_elapsed_s(event.clock) < LATE_S or level:
                continue
            behind = event.ctx.score_home < event.ctx.score_away
            if event.team == ("home" if behind else "away"):
                trailing += 1
            else:
                leading += 1
    assert trailing > 1.5 * leading
