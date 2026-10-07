from __future__ import annotations

import pytest

from footystreams.domain.rng import WorldRng, derive_seed

N_DRAWS = 2000


def _draw(rng: WorldRng, count: int = 8) -> list[float]:
    return [rng.u() for _ in range(count)]


def test_world_rng__same_seed__same_sequence() -> None:
    assert _draw(WorldRng(7)) == _draw(WorldRng(7))


def test_world_rng__different_seed__different_sequence() -> None:
    assert _draw(WorldRng(7)) != _draw(WorldRng(8))


def test_world_rng__known_vector__is_platform_stable() -> None:
    # Pinned so a change of algorithm (which would reshuffle every world) fails loudly.
    assert WorldRng(0).next_int() == 16294208416658607535


def test_world_rng__negative_seed__is_folded() -> None:
    assert WorldRng(-1).seed == (1 << 64) - 1


def test_fork__same_label__same_child_and_parent_untouched() -> None:
    parent = WorldRng(3)
    first = parent.fork("names")
    before = _draw(WorldRng(3), 3)
    second = parent.fork("names")
    assert _draw(first) == _draw(second)
    assert _draw(parent, 3) == before


def test_fork__different_labels__independent_streams() -> None:
    parent = WorldRng(3)
    assert _draw(parent.fork("a")) != _draw(parent.fork("b"))


def test_derive_seed__label_and_seed_both_matter() -> None:
    assert derive_seed(1, "x") != derive_seed(1, "y")
    assert derive_seed(1, "x") != derive_seed(2, "x")


def test_u__stays_in_unit_interval() -> None:
    rng = WorldRng(11)
    values = [rng.u() for _ in range(N_DRAWS)]
    assert all(0.0 <= value < 1.0 for value in values)


def test_u__mean_is_near_half() -> None:
    rng = WorldRng(11)
    mean = sum(rng.u() for _ in range(N_DRAWS)) / N_DRAWS
    assert abs(mean - 0.5) < 0.03


@pytest.mark.parametrize("bound", [0, -3])
def test_u_int__non_positive_bound__raises(bound: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        WorldRng(1).u_int(bound)


def test_randint__inclusive_bounds_are_reachable() -> None:
    rng = WorldRng(5)
    values = {rng.randint(2, 4) for _ in range(200)}
    assert values == {2, 3, 4}


def test_randint__inverted_bounds__raises() -> None:
    with pytest.raises(ValueError, match="low <= high"):
        WorldRng(1).randint(4, 2)


def test_uniform__stays_in_range() -> None:
    rng = WorldRng(2)
    assert all(10.0 <= rng.uniform(10.0, 12.5) < 12.5 for _ in range(200))


def test_bernoulli__extreme_probabilities_are_exact() -> None:
    rng = WorldRng(2)
    assert not any(rng.bernoulli(0.0) for _ in range(100))
    assert all(rng.bernoulli(1.0) for _ in range(100))


def test_gauss__is_roughly_standard_normal() -> None:
    rng = WorldRng(9)
    values = [rng.gauss() for _ in range(N_DRAWS)]
    mean = sum(values) / N_DRAWS
    variance = sum((value - mean) ** 2 for value in values) / N_DRAWS
    assert abs(mean) < 0.1
    assert abs(variance - 1.0) < 0.15


def test_truncated_normal__is_clamped() -> None:
    rng = WorldRng(9)
    assert all(40.0 <= rng.truncated_normal(50.0, 30.0, 40.0, 60.0) <= 60.0 for _ in range(200))


def test_beta__mean_matches_shape_ratio() -> None:
    rng = WorldRng(4)
    mean = sum(rng.beta(5, 3) for _ in range(N_DRAWS)) / N_DRAWS
    assert abs(mean - 5 / 8) < 0.03


@pytest.mark.parametrize(("alpha", "beta"), [(0, 1), (1, 0)])
def test_beta__invalid_shape__raises(alpha: int, beta: int) -> None:
    with pytest.raises(ValueError, match="positive integers"):
        WorldRng(1).beta(alpha, beta)


def test_choice__empty__raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        WorldRng(1).choice([])


def test_choice__single_item__returns_it() -> None:
    assert WorldRng(1).choice(["only"]) == "only"


def test_choice_weighted__follows_weights() -> None:
    rng = WorldRng(6)
    picks = [rng.choice_weighted({"a": 9.0, "b": 1.0}) for _ in range(N_DRAWS)]
    assert 0.85 < picks.count("a") / N_DRAWS < 0.95


def test_choice_weighted__ignores_dict_order() -> None:
    first = WorldRng(6).choice_weighted({"a": 1.0, "b": 1.0, "c": 1.0})
    second = WorldRng(6).choice_weighted({"c": 1.0, "b": 1.0, "a": 1.0})
    assert first == second


def test_choice_weighted__zero_weight_is_never_picked() -> None:
    rng = WorldRng(6)
    assert {rng.choice_weighted({"a": 0.0, "b": 1.0}) for _ in range(100)} == {"b"}


@pytest.mark.parametrize("weights", [{}, {"a": 0.0}])
def test_choice_weighted__no_positive_weight__raises(weights: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="positive weight"):
        WorldRng(1).choice_weighted(weights)


def test_shuffled__is_a_permutation_and_leaves_input_alone() -> None:
    items = list(range(20))
    result = WorldRng(8).shuffled(items)
    assert sorted(result) == items
    assert items == list(range(20))
    assert result != items
