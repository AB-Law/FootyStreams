from __future__ import annotations

from tests.factories.balance_runs import make_balance_scenarios


def test_build_scenarios__cycle_through_every_ordered_pairing_before_repeating() -> None:
    scenarios = make_balance_scenarios()

    pairs = [(s.setup.home.club.id, s.setup.away.club.id) for s in scenarios]

    assert len(set(pairs)) == len(pairs) == 12
    assert all(home != away for home, away in pairs)


def test_build_scenarios__match_seeds_count_up_from_the_base_seed() -> None:
    assert [s.seed for s in make_balance_scenarios()] == list(range(1, 13))


def test_build_scenarios__a_second_replicate_replays_the_pairings_in_new_conditions() -> None:
    scenarios = make_balance_scenarios(24)

    first, second = scenarios[0], scenarios[12]

    assert first.setup.home.club.id == second.setup.home.club.id
    assert first.setup.match_id == second.setup.match_id
    assert (first.setup.weather, first.setup.referee_id, first.setup.attendance) != (
        second.setup.weather,
        second.setup.referee_id,
        second.setup.attendance,
    )


def test_build_scenarios__swapping_the_venue_negates_the_gap() -> None:
    by_pair = {
        (s.setup.home.club.id, s.setup.away.club.id): s.gap for s in make_balance_scenarios()
    }

    for (home, away), gap in by_pair.items():
        assert abs(gap + by_pair[(away, home)]) < 1e-3
