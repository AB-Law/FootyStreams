from __future__ import annotations

import statistics

from footystreams.domain.rng import WorldRng
from footystreams.league.scouting import noise_sigma, perceive
from tests.factories.league_config import make_transfer_config
from tests.factories.world import make_world

CONFIG = make_transfer_config().scouting
PLAYER = make_world(1).players[0]


def _errors(judging: int, samples: int = 400) -> list[int]:
    return [
        perceive(PLAYER, judging, CONFIG, WorldRng(s)).ability - PLAYER.ability_current
        for s in range(samples)
    ]


def test_noise_sigma__full_at_zero_judging_and_none_at_one_hundred() -> None:
    assert noise_sigma(0, CONFIG) == CONFIG.noise_at_zero_judging
    assert noise_sigma(100, CONFIG) == 0.0


def test_perceive__perfect_judging__sees_the_truth() -> None:
    seen = perceive(PLAYER, 100, CONFIG, WorldRng(1))
    assert (seen.ability, seen.potential) == (PLAYER.ability_current, PLAYER.ability_potential)
    assert seen.confidence == 1.0


def test_perceive__noise_shrinks_as_judging_improves() -> None:
    poor, fair, great = (statistics.pstdev(_errors(j)) for j in (10, 50, 90))
    assert poor > fair > great


def test_perceive__estimates_are_unbiased_and_potential_is_noisier() -> None:
    errors = _errors(20)
    assert abs(statistics.mean(errors)) < 1.5
    potential_errors = [
        perceive(PLAYER, 20, CONFIG, WorldRng(s)).potential - PLAYER.ability_potential
        for s in range(400)
    ]
    assert statistics.pstdev(potential_errors) > statistics.pstdev(errors) * 0.9


def test_perceive__stays_in_range_and_potential_never_below_ability() -> None:
    for seed in range(200):
        seen = perceive(PLAYER, 0, CONFIG, WorldRng(seed))
        assert 1 <= seen.ability <= seen.potential <= 100


def test_perceive__same_stream__same_view() -> None:
    assert perceive(PLAYER, 30, CONFIG, WorldRng(5)) == perceive(PLAYER, 30, CONFIG, WorldRng(5))


def test_perceive__low_judging__confidence_has_a_floor() -> None:
    assert perceive(PLAYER, 0, CONFIG, WorldRng(1)).confidence == CONFIG.confidence_floor
