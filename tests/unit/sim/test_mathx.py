import pytest
from hypothesis import given
from hypothesis import strategies as st

from footystreams.sim.mathx import clamp, distance, lerp, rational_weight, squash


@given(st.floats(min_value=-1e6, max_value=1e6))
def test_squash__is_bounded_in_open_unit_interval(z: float) -> None:
    assert 0.0 <= squash(z) <= 1.0


@given(st.floats(min_value=-100, max_value=100), st.floats(min_value=0.001, max_value=10))
def test_squash__is_monotone(z: float, step: float) -> None:
    assert squash(z) <= squash(z + step)


def test_squash__is_half_at_zero() -> None:
    assert squash(0.0) == 0.5


@pytest.mark.parametrize(("value", "expected"), [(-1.0, 0.0), (0.5, 0.5), (3.0, 1.0)])
def test_clamp__limits_to_interval(value: float, expected: float) -> None:
    assert clamp(value, 0.0, 1.0) == expected


def test_lerp__interpolates_linearly() -> None:
    assert lerp(10.0, 20.0, 0.25) == 12.5


def test_distance__pythagorean_triple() -> None:
    assert distance(0.0, 0.0, 3.0, 4.0) == 5.0


def test_rational_weight__best_option_gets_the_largest_weight() -> None:
    best = rational_weight(1.0, 1.0, 2.0, 0.01)
    worse = rational_weight(0.5, 1.0, 2.0, 0.01)
    assert best == 1.0
    assert worse < best


def test_rational_weight__never_below_floor_power() -> None:
    assert rational_weight(-100.0, 1.0, 2.0, 0.1) > 0.0
