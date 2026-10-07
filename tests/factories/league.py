"""Builders for league-layer rows that sit on top of a generated world."""

from __future__ import annotations

import datetime as dt

from footystreams.domain.fixture import Fixture
from footystreams.domain.match import Match
from footystreams.domain.types import FixtureId, MatchId, StadiumId
from footystreams.domain.world import World
from tests.factories.match import make_setup


def make_fixture(world: World, matchday: int = 1, home: int = 0, away: int = 1) -> Fixture:
    """A scheduled fixture between two clubs of ``world`` in its first season."""
    season = world.seasons[0]
    return Fixture(
        id=FixtureId(f"fix_{matchday:02d}{home}{away}"),
        competition_id=season.competition_id,
        season_id=season.id,
        matchday=matchday,
        date=season.starts_on + dt.timedelta(days=7 * (matchday - 1)),
        home_club_id=world.clubs[home].id,
        away_club_id=world.clubs[away].id,
        stadium_id=StadiumId("std_00001"),
    )


def make_match(world: World, fixture: Fixture, match_id: str = "mch_test0001") -> Match:
    """A (not yet played) match record for ``fixture`` with factory sheets."""
    setup = make_setup()
    return Match(
        id=MatchId(match_id),
        fixture_id=fixture.id,
        competition_id=fixture.competition_id,
        season_id=fixture.season_id,
        matchday=fixture.matchday,
        date=fixture.date,
        venue_stadium_id=fixture.stadium_id,
        home_club_id=fixture.home_club_id,
        away_club_id=fixture.away_club_id,
        weather=setup.weather,
        referee_id=setup.referee_id,
        attendance=setup.attendance,
        home_sheet=setup.home,
        away_sheet=setup.away,
        seed=7,
        config_hash="b" * 64,
    )
