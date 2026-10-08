"""Tests for match stack models and factories."""

from __future__ import annotations

from footystreams.domain.match import MatchSetup, TeamSheet, players_on_both_sheets
from tests.factories.match import make_setup, make_team_sheet


def test_make_team_sheet__validates() -> None:
    sheet = make_team_sheet()
    assert len(sheet.lineup) == 11
    assert TeamSheet.model_validate_json(sheet.model_dump_json()) == sheet


def test_make_setup__validates() -> None:
    setup = make_setup()
    assert setup.home.club.id != setup.away.club.id
    assert MatchSetup.model_validate_json(setup.model_dump_json()) == setup
    assert setup.home.lineup[0].player_id in setup.home.squad


def test_players_on_both_sheets__distinct_teams__is_empty() -> None:
    assert players_on_both_sheets(make_setup()) == []


def test_players_on_both_sheets__shared_squad__lists_every_shared_id_sorted() -> None:
    home = make_team_sheet(club_id="clb_home01", side="home")
    setup = make_setup(home=home, away=home)

    assert players_on_both_sheets(setup) == sorted(home.squad)
