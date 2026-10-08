from __future__ import annotations

from collections.abc import Sequence

import pytest
import yaml

from footystreams.balance import knobs, nelder_mead
from footystreams.balance.fit import FitSettings, candidate_overrides, fit, format_candidate
from footystreams.balance.knobs import Knob
from footystreams.balance.sample import MatchSample
from footystreams.balance.targets import Target
from footystreams.sim import SimConfig
from tests.factories.balance import make_sample, make_side

GOALS = {"goals_per_match": Target(target=3.0, min=2.0, max=4.0)}  # half-width 1.0
SAMPLES = 100


def _goals_follow_the_xg_cap(config: SimConfig) -> list[MatchSample]:
    """Mean goals are ten times the xG cap, spread over 100 matches so the mean is continuous."""
    total = round(config.shot.xg_cap * 10 * SAMPLES)
    return [
        make_sample(
            make_side(goals=total // SAMPLES + (index < total % SAMPLES)), make_side(goals=0)
        )
        for index in range(SAMPLES)
    ]


def _goals_ignore_the_config(_: SimConfig) -> list[MatchSample]:
    return [make_sample(make_side(goals=1), make_side(goals=0))] * SAMPLES


def _bowl(point: Sequence[float]) -> float:
    return (point[0] - 0.7) ** 2 + (point[1] - 1.3) ** 2


def test_minimise__finds_the_minimum_of_a_smooth_function_inside_the_bounds() -> None:
    settings = nelder_mead.Settings(lower=0.5, upper=2.0, max_evaluations=200)

    found = nelder_mead.minimise(_bowl, [1.0, 1.0], settings)

    assert found.point == pytest.approx((0.7, 1.3), abs=0.01)
    assert found.value < 1e-4


def test_minimise__stays_on_the_boundary_when_the_minimum_is_outside_it() -> None:
    settings = nelder_mead.Settings(lower=0.5, upper=2.0)

    found = nelder_mead.minimise(lambda p: p[0], [1.0], settings)

    assert found.point == (0.5,)


def test_minimise__is_deterministic_and_respects_its_budget() -> None:
    settings = nelder_mead.Settings(lower=0.5, upper=2.0, max_evaluations=15)

    first = nelder_mead.minimise(_bowl, [1.0, 1.0], settings)

    assert first == nelder_mead.minimise(_bowl, [1.0, 1.0], settings)
    assert first.evaluations <= 15 + 2 + 2


def test_minimise__a_flat_objective_stops_at_once() -> None:
    found = nelder_mead.minimise(lambda _: 1.0, [1.0, 1.0, 1.0], nelder_mead.Settings())

    assert found.evaluations == 4


def test_fit__moves_a_knob_to_where_the_metric_meets_its_target() -> None:
    chosen = knobs.choose(SimConfig(), ["shot.xg_cap"])  # goals 4.0 at the default, target 3.0

    found = fit(
        _goals_follow_the_xg_cap, SimConfig(), chosen, GOALS, FitSettings(max_evaluations=40)
    )

    shot = found.overrides["shot"]
    assert isinstance(shot, dict)
    assert shot["xg_cap"] == pytest.approx(0.3, abs=0.01)
    assert found.loss_after < found.loss_before


def test_fit__a_flat_objective_changes_nothing() -> None:
    chosen = knobs.choose(SimConfig(), ["shot.xg_cap", "passing.base_back"])

    found = fit(
        _goals_ignore_the_config, SimConfig(), chosen, GOALS, FitSettings(max_evaluations=10)
    )

    assert found.overrides == {}
    assert found.loss_after == found.loss_before


def test_fit__restarts_are_reproducible_for_a_seed() -> None:
    chosen = knobs.choose(SimConfig(), ["shot.xg_cap"])
    settings = FitSettings(max_evaluations=30, restarts=2, seed=5)

    first = fit(_goals_follow_the_xg_cap, SimConfig(), chosen, GOALS, settings)
    second = fit(_goals_follow_the_xg_cap, SimConfig(), chosen, GOALS, settings)

    assert first == second


def test_candidate_overrides__lists_only_moved_knobs_at_four_significant_digits() -> None:
    chosen = [Knob("shot.xg_cap", 0.4), Knob("shot.range_m", 35.0)]

    found = candidate_overrides(chosen, {"shot.xg_cap": 0.7777777, "shot.range_m": 1.0})

    assert found == {"shot": {"xg_cap": 0.3111}}


def test_format_candidate__is_yaml_that_config_can_read_with_a_header() -> None:
    chosen = knobs.choose(SimConfig(), ["shot.xg_cap"])
    found = fit(
        _goals_follow_the_xg_cap, SimConfig(), chosen, GOALS, FitSettings(max_evaluations=40)
    )

    text = format_candidate(found, ["a note"])

    assert text.startswith("# a note\n# loss ")
    assert yaml.safe_load(text) == found.overrides


def test_format_candidate__nothing_moved_is_an_empty_mapping() -> None:
    chosen = knobs.choose(SimConfig(), ["shot.xg_cap"])
    found = fit(
        _goals_ignore_the_config, SimConfig(), chosen, GOALS, FitSettings(max_evaluations=5)
    )

    assert yaml.safe_load(format_candidate(found, [])) == {}
