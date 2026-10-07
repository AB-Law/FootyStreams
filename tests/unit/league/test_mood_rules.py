from __future__ import annotations

import datetime as dt
from dataclasses import replace
from typing import Any

from footystreams.domain.injury import Injury, InjurySeverity
from footystreams.domain.mood import ModifierSource, ModifierVisibility, StateKind
from footystreams.domain.types import MatchId, PlayerId
from footystreams.league.modifiers import ModifierSpec, new_modifier
from footystreams.league.mood_rules import (
    MatchFact,
    Outcome,
    modifier_for_return,
    modifiers_from_match,
)
from tests.factories.league_config import make_mood_config
from tests.factories.mood import TODAY

CONFIG = make_mood_config()
MATCH = MatchId("mch_00001")


QUIET = MatchFact(
    player_id=PlayerId("plr_00001"), goals=0, reds=0, rating=6.0, outcome=Outcome.DRAW, derby=False
)


def _fact(**changes: Any) -> MatchFact:
    return replace(QUIET, **changes)


def _kinds(*facts: MatchFact) -> list[StateKind]:
    return [m.kind for m in modifiers_from_match(facts, MATCH, TODAY, CONFIG)]


def test_modifiers_from_match__quiet_game__creates_nothing() -> None:
    assert _kinds(_fact()) == []


def test_modifiers_from_match__goal_in_a_derby_win__makes_a_derby_hero() -> None:
    assert StateKind.DERBY_HERO in _kinds(_fact(goals=1, derby=True, outcome=Outcome.WIN))


def test_modifiers_from_match__goal_in_a_derby_defeat__makes_no_hero() -> None:
    assert StateKind.DERBY_HERO not in _kinds(_fact(goals=1, derby=True, outcome=Outcome.LOSS))


def test_modifiers_from_match__two_goals_or_a_great_rating__builds_confidence() -> None:
    assert _kinds(_fact(goals=2)) == [StateKind.CONFIDENCE_SURGE]
    assert _kinds(_fact(rating=9.0)) == [StateKind.CONFIDENCE_SURGE]


def test_modifiers_from_match__red_card_in_a_defeat__blames_the_player() -> None:
    assert _kinds(_fact(reds=1, outcome=Outcome.LOSS)) == [StateKind.BLAMED_FOR_DEFEAT]
    assert _kinds(_fact(reds=1, outcome=Outcome.WIN)) == []


def test_modifiers_from_match__same_facts__same_rows() -> None:
    facts = [_fact(goals=2), _fact(player_id=PlayerId("plr_00002"), goals=2)]
    first = modifiers_from_match(facts, MATCH, TODAY, CONFIG)
    assert first == modifiers_from_match(list(reversed(facts)), MATCH, TODAY, CONFIG)
    assert len({m.id for m in first}) == 2


def test_new_modifier__private_kind__is_private_and_expires_after_default_days() -> None:
    modifier = new_modifier(
        ModifierSpec(StateKind.PERSONAL_TURMOIL, "plr_00001", 0.5, ModifierSource(origin="x")),
        TODAY,
        CONFIG,
    )
    assert modifier.visibility is ModifierVisibility.PRIVATE
    assert modifier.expires_on == TODAY + dt.timedelta(days=21)


def _injury(days: int) -> Injury:
    return Injury(
        type="x",
        body_part="knee",
        severity=InjurySeverity.SEVERE,
        started_on=TODAY - dt.timedelta(days=days),
        expected_return_on=TODAY,
    )


def test_modifier_for_return__long_injury__brings_joy() -> None:
    modifier = modifier_for_return(PlayerId("plr_00001"), _injury(60), TODAY, CONFIG)
    assert modifier is not None
    assert modifier.kind is StateKind.INJURY_RETURN_JOY


def test_modifier_for_return__short_injury__brings_nothing() -> None:
    assert modifier_for_return(PlayerId("plr_00001"), _injury(5), TODAY, CONFIG) is None
