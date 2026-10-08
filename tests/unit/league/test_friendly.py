"""A friendly: any two clubs set up like a league match, nothing written."""

from __future__ import annotations

import pytest

from footystreams.league.clock import read_date
from footystreams.league.friendly import build_friendly_setup, find_club
from footystreams.persistence.ports import NotFoundError
from tests.factories.league_db import make_league_db
from tests.factories.league_run import make_engine


def test_find_club__by_id_short_code_or_name_in_any_case() -> None:
    with make_league_db(2, 4)() as uow:
        club = uow.clubs.all()[0]

        assert find_club(uow, club.id) == club
        assert find_club(uow, club.short_code.lower()) == club
        assert find_club(uow, club.name.upper()) == club


def test_find_club__unknown__is_not_found() -> None:
    with make_league_db(2, 4)() as uow, pytest.raises(NotFoundError):
        find_club(uow, "Nowhere Rovers")


def test_build_friendly_setup__names_the_two_clubs_and_is_deterministic() -> None:
    with make_league_db(2, 4)() as uow:
        home, away = uow.clubs.all()[:2]
        today = read_date(uow)

        first = build_friendly_setup(uow, home.id, away.id, make_engine(2), today)
        second = build_friendly_setup(uow, home.id, away.id, make_engine(2), today)

    assert (first.home.club.id, first.away.club.id) == (home.id, away.id)
    assert first == second


def test_build_friendly_setup__writes_nothing_to_the_world() -> None:
    factory = make_league_db(2, 4)
    with factory() as uow:
        home, away = uow.clubs.all()[:2]
        today = read_date(uow)
        build_friendly_setup(uow, home.id, away.id, make_engine(2), today)
    with factory() as uow:
        assert uow.matches.all() == []
        assert {f.status.value for f in uow.fixtures.all()} <= {"scheduled"}
