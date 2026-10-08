from __future__ import annotations

import datetime as dt
from itertools import combinations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from footystreams.domain.rng import WorldRng
from footystreams.domain.types import ClubId, CompetitionId, SeasonId
from footystreams.league.schedule import (
    ScheduleError,
    build_rounds,
    circle_rounds,
    schedule_fixtures,
    stadium_id_for,
)
from footystreams.verify.schedule import check_schedule


def _clubs(count: int) -> list[ClubId]:
    return [ClubId(f"clb_{index:05d}") for index in range(1, count + 1)]


def _fixtures(count: int, seed: int, derbies=()):  # type: ignore[no-untyped-def]
    clubs = _clubs(count)
    rounds = build_rounds(clubs, WorldRng(seed), derbies)
    dates = [dt.date(2031, 8, 15) + dt.timedelta(days=21 * i) for i in range(len(rounds))]
    fixtures = schedule_fixtures(
        rounds, (CompetitionId("cmp_00001"), SeasonId("ssn_00001")), dates, derbies
    )
    return clubs, fixtures


@pytest.mark.parametrize("count", range(2, 21))
def test_build_rounds__valid_double_round_robin_for_every_league_size(count: int) -> None:
    clubs, fixtures = _fixtures(count, seed=count)
    assert check_schedule(fixtures, clubs) == []
    rounds = count - 1 if count % 2 == 0 else count
    assert max(f.matchday for f in fixtures) == 2 * rounds


@given(
    seed=st.integers(min_value=0, max_value=10_000), count=st.integers(min_value=4, max_value=16)
)
def test_build_rounds__any_seed_gives_a_valid_schedule(seed: int, count: int) -> None:
    clubs, fixtures = _fixtures(count, seed)
    assert check_schedule(fixtures, clubs) == []


def test_build_rounds__eight_clubs_play_fourteen_matchdays_of_four_matches() -> None:
    _, fixtures = _fixtures(8, seed=1)
    assert len(fixtures) == 56
    assert {f.matchday for f in fixtures} == set(range(1, 15))
    assert all(sum(f.matchday == day for f in fixtures) == 4 for day in range(1, 15))


def test_build_rounds__same_seed_same_schedule_different_seed_different_schedule() -> None:
    clubs = _clubs(8)
    assert build_rounds(clubs, WorldRng(3)) == build_rounds(clubs, WorldRng(3))
    assert build_rounds(clubs, WorldRng(3)) != build_rounds(clubs, WorldRng(4))


def test_build_rounds__derbies_are_never_on_matchday_one() -> None:
    clubs = _clubs(8)
    derbies = {frozenset({clubs[0], clubs[1]}), frozenset({clubs[2], clubs[6]})}
    for seed in range(15):
        first = build_rounds(clubs, WorldRng(seed), derbies)[0]
        assert not any(frozenset(pair) in derbies for pair in first)


def test_circle_rounds__every_pair_meets_exactly_once() -> None:
    clubs = _clubs(8)
    pairs = [frozenset(p) for matches in circle_rounds(clubs) for p in matches]
    assert sorted(map(sorted, pairs)) == sorted(map(sorted, map(frozenset, combinations(clubs, 2))))


def test_build_rounds__fewer_than_two_clubs__raises() -> None:
    with pytest.raises(ScheduleError, match="at least two"):
        build_rounds(_clubs(1), WorldRng(1))


def test_build_rounds__impossible_constraints_raise_after_the_attempt_budget() -> None:
    clubs = _clubs(2)
    # With two clubs every round is the only derby, so matchday 1 must contain one.
    with pytest.raises(ScheduleError, match="no valid schedule"):
        build_rounds(clubs, WorldRng(1), {frozenset(clubs)})


def test_schedule_fixtures__derby_pairs__are_flagged() -> None:
    rival = frozenset({ClubId("clb_00001"), ClubId("clb_00002")})
    _, fixtures = _fixtures(4, seed=1, derbies=[rival])
    flagged = {frozenset((f.home_club_id, f.away_club_id)) for f in fixtures if f.is_derby}
    assert flagged == {rival}


def test_schedule_fixtures__same_inputs__same_ids() -> None:
    first = _fixtures(6, seed=2)[1]
    assert [f.id for f in first] == [f.id for f in _fixtures(6, seed=2)[1]]


def test_schedule_fixtures__dates_ids_and_stadiums() -> None:
    _, fixtures = _fixtures(4, seed=1)
    assert fixtures[0].date == dt.date(2031, 8, 15)
    assert len({f.id for f in fixtures}) == len(fixtures)
    assert all(f.stadium_id == stadium_id_for(f.home_club_id) for f in fixtures)
    assert stadium_id_for(ClubId("clb_00004")) == "std_00004"


def test_check_schedule__flags_each_kind_of_defect() -> None:
    clubs, fixtures = _fixtures(4, seed=1)
    broken = [
        f.model_copy(update={"away_club_id": f.home_club_id}) if i == 0 else f
        for i, f in enumerate(fixtures)
    ]
    assert {v.code for v in check_schedule(broken, clubs)} == {"W12"}
    assert check_schedule(fixtures[:-1], clubs)  # a missing fixture
    duplicated = [fixtures[0], fixtures[0].model_copy(update={"id": "fix_dup0001"}), *fixtures[1:]]
    assert check_schedule(duplicated, clubs)
    derby = frozenset({fixtures[0].home_club_id, fixtures[0].away_club_id})
    assert any("derby" in v.message for v in check_schedule(fixtures, clubs, {derby}))
    same_day = [f.model_copy(update={"matchday": 1}) for f in fixtures]
    assert any("times on matchday" in v.message for v in check_schedule(same_day, clubs))
