"""Statistical sanity of strength: stronger teams win more, and gaps do not explode into rout."""

import pytest

from footystreams.sim import SimConfig, default_tables, run_match
from tests.factories.sim_teams import make_demo_setup

TABLES = default_tables()
CFG = SimConfig()


def _record(home_strength: int, away_strength: int, matches: int) -> tuple[int, int, int]:
    setup = make_demo_setup(home_strength=home_strength, away_strength=away_strength)
    wins = draws = losses = 0
    for seed in range(matches):
        summary = run_match(setup, seed, CFG, TABLES).summary
        wins += summary.score_home > summary.score_away
        draws += summary.score_home == summary.score_away
        losses += summary.score_home < summary.score_away
    return wins, draws, losses


@pytest.mark.slow
@pytest.mark.statistical
def test_strength__much_stronger_home_side_wins_most_and_rarely_loses() -> None:
    wins, _, losses = _record(72, 54, 8)
    assert wins >= 5
    assert losses <= 1


@pytest.mark.slow
@pytest.mark.statistical
def test_strength__equal_teams_both_win_some_and_the_stronger_side_wins_more_than_it_loses() -> (
    None
):
    even_wins, _, even_losses = _record(60, 60, 12)
    strong_wins, _, strong_losses = _record(66, 54, 12)
    assert even_wins >= 1
    assert even_losses >= 1
    assert strong_wins - strong_losses > even_wins - even_losses


@pytest.mark.slow
@pytest.mark.statistical
@pytest.mark.timeout(600)
def test_strength__favourite_win_rate_rises_with_the_gap_and_goals_stay_plausible() -> None:
    rates = []
    for gap in (4, 12, 24):
        wins, draws, losses = _record(60 + gap // 2, 60 - gap // 2, 60)
        rates.append(wins / (wins + draws + losses))
    assert rates[0] < rates[1] < rates[2]
    assert rates[2] < 0.97


@pytest.mark.slow
@pytest.mark.statistical
@pytest.mark.timeout(600)
def test_balance__goals_shots_and_conversion_sit_in_loose_sanity_bands() -> None:
    setup = make_demo_setup()
    goals = shots = 0
    matches = 60
    for seed in range(matches):
        summary = run_match(setup, seed, CFG, TABLES).summary
        goals += summary.score_home + summary.score_away
        shots += summary.team_stats_home.shots + summary.team_stats_away.shots
    assert 1.8 < goals / matches < 4.2
    assert 18 < shots / matches < 36
    assert 0.06 < goals / shots < 0.16


@pytest.mark.slow
@pytest.mark.statistical
@pytest.mark.timeout(600)
def test_strength__equal_teams_split_wins_evenly_over_a_large_sample() -> None:
    matches = 80
    wins, _, losses = _record(60, 60, matches)
    # About 49 of 80 matches are decided; the difference has a standard deviation of about 7,
    # so 15 is roughly two sd: loose enough for a fixed seed set, tight enough to catch a side bias.
    assert abs(wins - losses) <= 15
