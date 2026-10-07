from __future__ import annotations

import datetime as dt
from collections.abc import Mapping

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from footystreams.domain.attributes import attribute_map
from footystreams.domain.injury import InjuryRecord, InjurySeverity
from footystreams.domain.player import Player
from footystreams.domain.ratings import compute_current_ability
from footystreams.domain.rng import WorldRng
from footystreams.league.development import GROUPS, Conditions, headroom
from footystreams.league.progression import (
    ProgressionInputs,
    micro_step,
    progress_season,
    refresh,
    revise_potential,
)
from tests.factories.league_config import make_development_config
from tests.factories.world import cached_static_tables, make_world

TODAY = dt.date(2032, 6, 1)
CONFIG = make_development_config()
ROLES = cached_static_tables().roles
INPUTS = ProgressionInputs(CONFIG, ROLES, TODAY)
GOOD = Conditions(training=dict.fromkeys(GROUPS, 0.8), playing_time=0.9)
PLAYERS = [p for p in make_world(1).players if p.primary_position.value != "GK" and not p.is_youth]


def aged(player: Player, age: int) -> Player:
    """The player with a birth date that makes him ``age`` on TODAY."""
    born = TODAY.replace(year=TODAY.year - age) - dt.timedelta(days=100)
    return player.model_copy(update={"date_of_birth": born})


def with_room(player: Player, potential: int = 95) -> Player:
    """Plenty of headroom so growth is not capped."""
    return player.model_copy(update={"ability_potential": max(player.ability_current, potential)})


def total(player: Player, groups: tuple[str, ...] = GROUPS[:3]) -> int:
    return sum(sum(attribute_map(getattr(player, g)).values()) for g in groups)


def mean_change(age: int, groups: tuple[str, ...] = GROUPS[:3], count: int = 24) -> float:
    changes = []
    for index, base in enumerate(PLAYERS[:count]):
        player = with_room(aged(base, age))
        moved, _ = progress_season(player, GOOD, INPUTS, WorldRng(index))
        changes.append(total(moved, groups) - total(player, groups))
    return sum(changes) / len(changes)


def test_progress_season__teenagers__grow_and_veterans__decline() -> None:
    assert mean_change(18) > 20
    assert mean_change(34) < -15


def test_progress_season__prime_years__grow_far_less_than_youth() -> None:
    assert 0 <= mean_change(28) < mean_change(22) / 2


def test_progress_season__physical_declines_earlier_than_mental() -> None:
    assert mean_change(31, ("physical",)) < mean_change(31, ("mental",))


def test_progress_season__peak_age_of_growth__physical_peaks_before_technical() -> None:
    physical = [mean_change(a, ("physical",)) for a in (20, 24, 28)]
    technical = [mean_change(a, ("technical",)) for a in (20, 24, 28)]
    assert physical[0] > physical[1] > physical[2]
    assert technical[1] > physical[1]


def test_progress_season__no_headroom__no_growth() -> None:
    player = aged(PLAYERS[0], 20)
    capped = player.model_copy(update={"ability_potential": player.ability_current})
    assert headroom(capped, CONFIG.progression) == 0.0
    moved, _ = progress_season(capped, GOOD, INPUTS, WorldRng(1))
    assert moved.ability_current <= capped.ability_current


@settings(max_examples=40, deadline=None)
@given(index=st.integers(0, 60), age=st.integers(16, 38), seed=st.integers(0, 10**6))
def test_progress_season__ability_never_exceeds_potential(index: int, age: int, seed: int) -> None:
    player = aged(PLAYERS[index % len(PLAYERS)], age)
    moved, _ = progress_season(player, GOOD, INPUTS, WorldRng(seed))
    assert moved.ability_current <= moved.ability_potential
    assert moved.ability_current == compute_current_ability(moved, ROLES)


def _attributes(player: Player) -> Mapping[str, int]:
    return {n: v for g in GROUPS for n, v in attribute_map(getattr(player, g)).items()}


@settings(max_examples=30, deadline=None)
@given(index=st.integers(0, 60), age=st.integers(16, 38), seed=st.integers(0, 10**6))
def test_progress_season__the_journal_explains_every_attribute_delta(
    index: int, age: int, seed: int
) -> None:
    player = aged(PLAYERS[index % len(PLAYERS)], age)
    moved, entries = progress_season(player, GOOD, INPUTS, WorldRng(seed))
    before, after = _attributes(player), _attributes(moved)
    explained: dict[str, int] = {}
    for entry in entries:
        explained[entry.attr] = explained.get(entry.attr, 0) + entry.delta
    moved_attrs = {
        name: after[name] - before[name] for name in before if after[name] != before[name]
    }
    assert moved_attrs == {name: delta for name, delta in explained.items() if delta}


def test_progress_season__same_inputs__same_result() -> None:
    player = aged(PLAYERS[3], 22)
    first = progress_season(player, GOOD, INPUTS, WorldRng(5))
    assert first == progress_season(player, GOOD, INPUTS, WorldRng(5))


def test_progress_season__better_training_and_more_games__grow_faster() -> None:
    poor = Conditions(training=dict.fromkeys(GROUPS, 0.0), playing_time=0.0)
    rich_total = poor_total = 0
    for index, base in enumerate(PLAYERS[:20]):
        player = with_room(aged(base, 19))
        rich_total += total(progress_season(player, GOOD, INPUTS, WorldRng(index))[0])
        poor_total += total(progress_season(player, poor, INPUTS, WorldRng(index))[0])
    assert rich_total > poor_total


def test_progress_season__severe_injury_in_the_year__costs_physical_points() -> None:
    record = InjuryRecord(
        type="achilles_rupture", body_part="achilles", severity=InjurySeverity.SEVERE,
        started_on=TODAY - dt.timedelta(days=200), returned_on=TODAY - dt.timedelta(days=20),
    )  # fmt: skip
    hurt = with_room(aged(PLAYERS[0], 27)).model_copy(update={"injury_history": (record,)})
    entries = [
        e for seed in range(12) for e in progress_season(hurt, GOOD, INPUTS, WorldRng(seed))[1]
    ]
    assert any(e.cause == "injury_setback" and e.delta < 0 for e in entries)


def test_micro_step__a_week_of_training__moves_at_most_a_few_points_and_explains_them() -> None:
    player = with_room(aged(PLAYERS[2], 18))
    gained = 0
    for seed in range(200):
        moved, entries = micro_step(player, GOOD, INPUTS, WorldRng(seed))
        assert all(e.cause == "training" and e.delta == 1 for e in entries)
        assert moved.ability_current <= moved.ability_potential
        gained += len(entries)
    assert 0 < gained / 200 < 4


def test_micro_step__a_veteran_with_no_room__does_nothing() -> None:
    player = aged(PLAYERS[2], 35)
    assert micro_step(player, GOOD, INPUTS, WorldRng(1)) == (player, ())


def test_revise_potential__only_young_players_and_never_below_ability() -> None:
    old = aged(PLAYERS[0], 30)
    assert all(revise_potential(old, INPUTS, WorldRng(s)) is old for s in range(30))
    young = aged(PLAYERS[0], 19)
    results = [revise_potential(young, INPUTS, WorldRng(s)) for s in range(300)]
    assert any(r.ability_potential != young.ability_potential for r in results)
    assert all(r.ability_current <= r.ability_potential <= 100 for r in results)


def test_refresh__recomputes_ability_and_value_from_attributes() -> None:
    player = PLAYERS[0]
    stale = player.model_copy(update={"ability_current": 1, "market_value": 0})
    fresh = refresh(stale, ROLES, TODAY)
    assert fresh.ability_current == compute_current_ability(player, ROLES)
    assert fresh.market_value > 0


@pytest.mark.parametrize("group", GROUPS[:3])
def test_conditions__every_group_has_a_curve(group: str) -> None:
    assert group in CONFIG.progression.curves
