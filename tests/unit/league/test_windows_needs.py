from __future__ import annotations

import datetime as dt

from footystreams.domain.player import Player
from footystreams.domain.transfer import WindowKind
from footystreams.domain.types import Position
from footystreams.league.needs import GROUPS, analyse, group_of
from footystreams.league.transfer_windows import days_left, open_window, windows_for
from tests.factories.league_config import make_league_config, make_transfer_config
from tests.factories.league_inputs import make_league_tables
from tests.factories.world import make_world

WORLD = make_world(1)
CALENDAR = make_league_config().calendar
NEEDS = make_transfer_config().needs
SEASON = WORLD.seasons[0]


def test_windows_for__a_summer_window_before_the_season_and_one_in_the_middle() -> None:
    summer, mid = windows_for(SEASON, CALENDAR)
    assert (summer.kind, mid.kind) == (WindowKind.SUMMER, WindowKind.MIDSEASON)
    assert summer.opens_on == dt.date(2031, 6, 15)
    assert summer.closes_on == dt.date(2031, 8, 14) < SEASON.starts_on
    assert SEASON.starts_on < mid.opens_on < mid.closes_on < SEASON.ends_on
    assert summer.id != mid.id


def test_windows_for__ids_depend_only_on_the_season_and_kind() -> None:
    assert [w.id for w in windows_for(SEASON, CALENDAR)] == [
        w.id for w in windows_for(SEASON, CALENDAR)
    ]


def test_open_window__finds_the_window_containing_the_day() -> None:
    windows = windows_for(SEASON, CALENDAR)
    assert open_window(windows, dt.date(2031, 7, 1)) == windows[0]
    assert open_window(windows, windows[1].opens_on) == windows[1]
    assert open_window(windows, dt.date(2031, 9, 20)) is None


def test_days_left__counts_to_the_closing_day() -> None:
    summer = windows_for(SEASON, CALENDAR)[0]
    assert days_left(summer, summer.closes_on) == 0
    assert days_left(summer, summer.closes_on - dt.timedelta(days=3)) == 3


def test_group_of__every_position_belongs_to_exactly_one_group() -> None:
    assert {group_of(p) for p in Position} == set(GROUPS)
    assert sum(len(members) for members in GROUPS.values()) == len(Position)


def _formation() -> list[Position]:
    tables = make_league_tables()
    club = WORLD.clubs[0]
    return list(tables.formations.formations[club.default_tactics.formation].positions())


def _squad() -> list[Player]:
    return [
        p
        for p in WORLD.players
        if p.contract and p.contract.club_id == WORLD.clubs[0].id and not p.is_youth
    ]


def test_analyse__a_full_squad_has_only_mild_needs() -> None:
    needs = analyse(_squad(), _formation(), NEEDS)
    assert all(need.urgency < 1.0 for need in needs)
    assert needs == sorted(needs, key=lambda n: (-n.urgency, n.group))


def test_analyse__a_group_below_its_minimum_is_urgent() -> None:
    no_keepers = [p for p in _squad() if p.primary_position is not Position.GK]
    needs = analyse(no_keepers, _formation(), NEEDS)
    assert needs[0].group == "GK"
    assert needs[0].urgency == 1.0
    assert Position.GK in needs[0].positions


def test_analyse__a_weak_starter_asks_for_a_better_player() -> None:
    squad = _squad()
    strikers = sorted(
        (p for p in squad if p.primary_position in GROUPS["FWD"]), key=lambda p: p.ability_current
    )
    weakened = [
        p.model_copy(update={"ability_current": 20, "ability_potential": 30})
        if p in strikers[:4]
        else p
        for p in squad
    ]
    needs = {n.group: n for n in analyse(weakened, _formation(), NEEDS)}
    assert needs["FWD"].urgency > 0.0
    assert needs["FWD"].min_quality >= 20 + NEEDS.upgrade_margin


def test_analyse__no_players_means_every_group_is_urgent() -> None:
    needs = analyse([], _formation(), NEEDS)
    assert {n.group for n in needs} == set(GROUPS)
    assert all(n.urgency == 1.0 for n in needs)
