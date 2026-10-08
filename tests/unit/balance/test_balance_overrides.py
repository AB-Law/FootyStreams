from __future__ import annotations

import pytest

from footystreams.balance import overrides
from footystreams.sim import SimConfig


def test_nest__builds_a_nested_mapping_from_a_dotted_path() -> None:
    assert overrides.nest("shot.xg_cap", 0.3) == {"shot": {"xg_cap": 0.3}}
    assert overrides.nest("home_advantage_scale", 2) == {"home_advantage_scale": 2}


def test_parse_pair__reads_the_value_as_a_yaml_scalar() -> None:
    assert overrides.parse_pair("shot.xg_cap=0.35") == {"shot": {"xg_cap": 0.35}}
    assert overrides.parse_pair("emit_frames=true") == {"emit_frames": True}


@pytest.mark.parametrize("bad", ["shot.xg_cap", "=3"])
def test_parse_pair__without_a_path_or_value_is_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match=r"group\.knob=value"):
        overrides.parse_pair(bad)


def test_combine__later_layers_win_and_siblings_survive() -> None:
    first = {"shot": {"xg_cap": 0.3, "range_m": 30}}

    combined = overrides.combine([first, {"shot": {"xg_cap": 0.2}}])

    assert combined == {"shot": {"xg_cap": 0.2, "range_m": 30}}
    assert first == {"shot": {"xg_cap": 0.3, "range_m": 30}}


def test_apply__changes_the_named_knob_and_nothing_else() -> None:
    config = overrides.apply(SimConfig(), {"shot": {"xg_cap": 0.3}})

    assert config.shot.xg_cap == 0.3
    assert config.shot.range_m == SimConfig().shot.range_m


def test_apply__no_overrides_returns_the_base() -> None:
    base = SimConfig()

    assert overrides.apply(base, {}) is base


@pytest.mark.parametrize("bad", [{"shot": {"no_such_knob": 1}}, {"shot": {"xg_cap": -1}}])
def test_apply__an_unknown_or_out_of_range_knob_is_a_value_error(bad: dict[str, object]) -> None:
    with pytest.raises(ValueError):  # noqa: PT011 - a pydantic ValidationError is a ValueError
        overrides.apply(SimConfig(), bad)
