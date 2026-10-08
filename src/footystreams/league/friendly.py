"""A friendly: any two clubs of a world, set up like a league match but outside the schedule.

Why this exists: ``uv run sim --home A --away B`` needs a real ``MatchSetup`` (weather, referee,
crowd, lineups) without playing a fixture, so nothing is written to the world. The setup comes from
the same code as a league match, so a friendly is exactly what that fixture would have been.
"""

from __future__ import annotations

import datetime as dt

from footystreams.domain.club import Club
from footystreams.domain.competition import Season
from footystreams.domain.fixture import Fixture
from footystreams.domain.match import MatchSetup
from footystreams.domain.rng import WorldRng, derive_seed
from footystreams.domain.types import ClubId, FixtureId
from footystreams.league.matchday import MatchdayEngine, build_fixture_setup
from footystreams.league.schedule import stadium_id_for
from footystreams.league.season import current_season
from footystreams.persistence.ports import NotFoundError, Repositories

FRIENDLY_MATCHDAY = 1
CLUB_ID_PREFIX = "clb_"


class AmbiguousClubError(ValueError):
    """More than one club answers to the name given."""


def find_club(repositories: Repositories, text: str) -> Club:
    """The club whose id, short code or name (any case) is ``text``."""
    wanted = text.strip().casefold()
    found = [
        club
        for club in repositories.clubs.all()
        if wanted in {club.id.casefold(), club.short_code.casefold(), club.name.casefold()}
    ]
    if not found:
        raise NotFoundError("clubs", text)
    if len(found) > 1:
        msg = f"{text!r} matches {len(found)} clubs: {', '.join(club.id for club in found)}"
        raise AmbiguousClubError(msg)
    return found[0]


def friendly_fixture(home: ClubId, away: ClubId, season: Season, today: dt.date) -> Fixture:
    """A throw-away fixture for the pairing; its id is derived from the two clubs."""
    suffix = f"{home.removeprefix(CLUB_ID_PREFIX)}_{away.removeprefix(CLUB_ID_PREFIX)}"
    return Fixture(
        id=FixtureId(f"fix_friendly_{suffix}"),
        competition_id=season.competition_id,
        season_id=season.id,
        matchday=FRIENDLY_MATCHDAY,
        date=today,
        home_club_id=home,
        away_club_id=away,
        stadium_id=stadium_id_for(home),
    )


def build_friendly_setup(
    repositories: Repositories,
    home: ClubId,
    away: ClubId,
    engine: MatchdayEngine,
    today: dt.date,
) -> MatchSetup:
    """The setup of ``home`` v ``away`` as of ``today``; deterministic in the world seed."""
    fixture = friendly_fixture(home, away, current_season(repositories, today), today)
    rng = WorldRng(derive_seed(engine.world_seed, f"match:{fixture.id}"))
    return build_fixture_setup(repositories, fixture, engine, today, rng)[0]
