from __future__ import annotations

import pytest

from footystreams.balance import knobs
from footystreams.balance.evaluate import evaluate
from footystreams.balance.knobs import Knob
from footystreams.balance.sample import MatchSample
from footystreams.balance.sensitivity import (
    Sensitivity,
    format_matrix,
    noise_floor,
    strongest,
    sweep,
)
from footystreams.balance.targets import Target
from footystreams.sim import SimConfig
from tests.factories.balance import make_sample, make_side

GOALS = {"goals_per_match": Target(target=2.0, min=1.0, max=3.0)}  # half-width 1.0


def _goals_follow_the_xg_cap(config: SimConfig) -> list[MatchSample]:
    """A stand-in for a simulation in which goals are exactly ten times the xG cap."""
    goals = round(config.shot.xg_cap * 10)
    return [make_sample(make_side(goals=goals), make_side(goals=0))] * 20


def test_discover__finds_the_float_knobs_with_their_defaults() -> None:
    found = {knob.path: knob.default for knob in knobs.discover(SimConfig())}

    assert found["shot.xg_cap"] == SimConfig().shot.xg_cap
    assert found["home_advantage_scale"] == 1.0
    assert "emit_frames" not in found
    assert "decision.candidates" not in found  # an int is not a knob


def test_choose__returns_the_named_knobs_and_rejects_unknown_ones() -> None:
    assert [k.path for k in knobs.choose(SimConfig(), ["shot.xg_cap"])] == ["shot.xg_cap"]

    with pytest.raises(ValueError, match=r"shot\.nope"):
        knobs.choose(SimConfig(), ["shot.nope"])


def test_with_multipliers__scales_the_default_and_leaves_the_rest() -> None:
    chosen = knobs.choose(SimConfig(), ["shot.xg_cap"])

    config = knobs.with_multipliers(SimConfig(), chosen, {"shot.xg_cap": 0.5})

    assert config.shot.xg_cap == pytest.approx(0.2)
    assert config.shot.range_m == SimConfig().shot.range_m


def test_with_multipliers__an_illegal_value_is_a_value_error() -> None:
    chosen = knobs.choose(SimConfig(), ["shot.xg_cap"])

    with pytest.raises(ValueError):  # noqa: PT011 - a pydantic ValidationError is a ValueError
        knobs.with_multipliers(SimConfig(), chosen, {"shot.xg_cap": -1.0})


def test_sweep__reports_the_effect_across_the_nudge_in_band_half_widths() -> None:
    chosen = knobs.choose(SimConfig(), ["shot.xg_cap"])  # 0.4: x0.8 = 3 goals... x1.2 = 5 goals

    (result,) = sweep(_goals_follow_the_xg_cap, SimConfig(), chosen, GOALS, relative=0.2)

    assert result.effects is not None
    assert result.effects["goals_per_match"] == pytest.approx(2.0)


def test_sweep__a_knob_with_one_illegal_side_uses_the_other_side_doubled() -> None:
    chosen = knobs.choose(SimConfig(), ["passing.base_back"])  # 1.0: x1.2 is above its maximum

    (result,) = sweep(_goals_follow_the_xg_cap, SimConfig(), chosen, GOALS)

    assert result.effects is not None
    assert result.effects["goals_per_match"] == pytest.approx(0.0)


def test_sweep__a_knob_with_no_legal_nudge_is_reported_as_unmoveable() -> None:
    stuck = Knob("shot.xg_cap", -1.0)  # both nudged values are negative: refused

    (result,) = sweep(_goals_follow_the_xg_cap, SimConfig(), [stuck], GOALS)

    assert result.effects is None


def test_strongest__orders_knobs_by_absolute_effect_and_skips_unmoveable_ones() -> None:
    items = [
        Sensitivity(Knob("a", 1.0), {"goals_per_match": 0.5}),
        Sensitivity(Knob("b", 1.0), {"goals_per_match": -3.0}),
        Sensitivity(Knob("c", 1.0), None),
    ]

    assert [s.knob.path for s in strongest(items, "goals_per_match", 5)] == ["b", "a"]


def test_format_matrix__marks_effects_larger_than_the_noise() -> None:
    items = [Sensitivity(Knob("shot.xg_cap", 0.4), {"goals_per_match": 2.0})]
    base = evaluate(_goals_follow_the_xg_cap(SimConfig()), GOALS)

    text = format_matrix(items, ["goals_per_match"], noise_floor(base))

    assert "shot.xg_cap" in text
    assert "+2.00*" in text


def test_format_matrix__says_when_a_knob_has_no_legal_change() -> None:
    text = format_matrix([Sensitivity(Knob("x.y", 1.0), None)], ["goals_per_match"], {})

    assert "no legal change" in text
