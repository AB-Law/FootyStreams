"""M5 sweeps: every event type shows up, invariants hold across matches, rates stay sane."""

from collections import Counter
from collections.abc import Iterator

import pytest

from footystreams.domain.match import MatchSetup
from footystreams.events.discipline import CardEvent
from footystreams.events.restarts import PenaltyEvent
from footystreams.events.result import MatchResult
from footystreams.events.structure import AddedTimeEvent
from footystreams.sim import SimConfig, default_tables, run_match
from footystreams.verify import verify_match
from tests.factories.referee import make_referee
from tests.factories.sim_teams import make_demo_setup

pytestmark = [pytest.mark.slow, pytest.mark.statistical, pytest.mark.timeout(1200)]

TABLES = default_tables()
CFG = SimConfig()
FORMATIONS = sorted(TABLES.formations)
EMITTED_BY_M5 = {
    "kickoff", "added_time", "halftime", "fulltime", "match_summary", "pass", "dribble",
    "tackle", "interception", "clearance", "shot", "save", "goal", "offside", "foul", "card",
    "throw_in", "goal_kick", "corner", "free_kick", "penalty",
}  # fmt: skip


def _sweep(matches: int) -> Iterator[tuple[MatchSetup, MatchResult]]:
    for index in range(matches):
        setup = make_demo_setup(
            home_strength=54 + (index * 7) % 17,
            away_strength=54 + (index * 11) % 17,
            home_formation=FORMATIONS[index % 8],
            away_formation=FORMATIONS[(index * 3 + 1) % 8],
        )
        yield setup, run_match(setup, 500 + index, CFG, TABLES)


def test_sweep__every_m5_event_type_appears_and_every_log_is_valid() -> None:
    seen: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    matches = 300
    for setup, result in _sweep(matches):
        assert verify_match(result.events, setup) == []
        seen.update(event.type for event in result.events)
        totals["penalty_goals"] += sum(
            isinstance(e, PenaltyEvent) and e.outcome == "goal" for e in result.events
        )
    missing = EMITTED_BY_M5 - set(seen)
    assert not missing, f"never emitted in {matches} matches: {sorted(missing)}"
    penalties = seen["penalty"]
    assert 0.08 < penalties / matches < 0.6
    assert 0.6 < totals["penalty_goals"] / penalties < 0.92
    assert 15 < seen["foul"] / matches < 32
    assert 5 < seen["corner"] / matches < 15
    assert 1.5 < seen["offside"] / matches < 7


def test_sweep__cards_are_consistent_and_added_time_is_sensible() -> None:
    yellows = reds = 0
    added: list[int] = []
    matches = 120
    for _, result in _sweep(matches):
        for event in result.events:
            if isinstance(event, CardEvent):
                yellows += event.colour != "red"
                reds += event.colour != "yellow"
            if isinstance(event, AddedTimeEvent):
                added.append(event.minutes)
    assert 2.0 < yellows / matches < 5.5
    assert 0.03 < reds / matches < 0.4
    assert min(added) >= 1.0
    assert max(added) <= 10
    assert 1.0 < sum(added) / len(added) < 6.0


def _foul_card_rate(strictness: float, matches: int) -> tuple[float, float]:
    referee = make_referee(strictness=strictness, card_tendency=strictness)
    fouls = cards = 0
    for index in range(matches):
        setup = make_demo_setup()
        result = run_match(setup, 900 + index, CFG, TABLES, referee)
        fouls += sum(e.type == "foul" for e in result.events)
        cards += sum(e.type == "card" for e in result.events)
    return fouls / matches, cards / matches


def test_referee__a_strict_referee_gives_more_fouls_and_cards_than_a_lenient_one() -> None:
    strict_fouls, strict_cards = _foul_card_rate(1.0, 100)
    lenient_fouls, lenient_cards = _foul_card_rate(0.0, 100)
    assert strict_fouls > lenient_fouls
    assert strict_cards > lenient_cards


def test_referee__a_home_biased_referee_punishes_the_away_side_more() -> None:
    biased = make_referee(home_bias=0.5)
    home_fouls = away_fouls = 0
    for index in range(100):
        result = run_match(make_demo_setup(), 1300 + index, CFG, TABLES, biased)
        fouls = [e for e in result.events if e.type == "foul"]
        home_fouls += sum(e.team == "home" for e in fouls)
        away_fouls += sum(e.team == "away" for e in fouls)
    assert away_fouls > home_fouls
