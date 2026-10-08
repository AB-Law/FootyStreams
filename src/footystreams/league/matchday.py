"""Play fixtures: weather, crowd, referee, setup, simulation and the resulting delta.

One fixture is one transaction (the caller owns it): everything the match changes is applied
together or not at all. The simulator is the ``MatchSimulator`` seam, so this works the same with
the result-only simulator and the real event simulator.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.domain.club import Club
from footystreams.domain.fixture import Fixture, FixtureStatus
from footystreams.domain.match import MatchSetup
from footystreams.domain.rng import WorldRng, derive_seed
from footystreams.domain.standings import MatchScore, StandingRow
from footystreams.domain.types import ClubId, RefereeId, SeasonId
from footystreams.domain.weather import Weather
from footystreams.league.attendance import CrowdInputs, attendance
from footystreams.league.delta import WorldDelta, apply_delta
from footystreams.league.inputs import load_team
from footystreams.league.post_match import PlayedFixture, derive_world_delta
from footystreams.league.setup import MatchContext, TeamInputs, build_match_setup
from footystreams.league.simulator import MatchSimulator
from footystreams.league.standings import compute_table
from footystreams.league.tables import LeagueTables
from footystreams.league.weather_gen import generate_weather
from footystreams.persistence.ports import NotFoundError, Repositories, StandingsSnapshot

SCHEDULED = FixtureStatus.SCHEDULED.value
SEED_LIMIT = 2**63  # a match seed is stored in a signed 64-bit column
COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class MatchdayEngine:
    """What playing a fixture needs besides the database."""

    tables: LeagueTables
    simulator: MatchSimulator
    world_seed: int


def due_fixtures(repositories: Repositories, today: dt.date) -> list[Fixture]:
    """Fixtures dated ``today`` that have not been played, in id order."""
    return repositories.fixtures.find({"date": today, "status": SCHEDULED})


def _climate_key(repositories: Repositories, club: Club) -> str:
    cities = repositories.cities.find(
        {"nation_id": club.location.nation_id, "name": club.location.city}
    )
    if not cities:
        raise NotFoundError("cities", f"{club.location.nation_id}/{club.location.city}")
    return cities[0].climate


def _weather(
    repositories: Repositories, home: Club, today: dt.date, engine: MatchdayEngine, rng: WorldRng
) -> Weather:
    config = engine.tables.config.weather
    hour = rng.choice(config.kickoff_hours)
    band = engine.tables.climate.bands[_climate_key(repositories, home)]
    return generate_weather(
        band, dt.datetime.combine(today, dt.time(hour)), rng.fork("weather"), config
    )


def _referee(repositories: Repositories, rng: WorldRng) -> RefereeId:
    return RefereeId(rng.choice(repositories.referees.all()).id)


def _crowd(
    home: TeamInputs, fixture: Fixture, weather: Weather, engine: MatchdayEngine, rng: WorldRng
) -> int:
    squad = home.squad
    form = sum(p.form for p in squad) / len(squad) if squad else 0.5
    inputs = CrowdInputs(
        stadium=home.club.stadium,
        fanbase=home.club.fanbase,
        reputation=home.club.club_reputation,
        form=form,
        derby=fixture.is_derby,
        weather=weather,
    )
    return attendance(inputs, rng.fork("attendance"), engine.tables.config.attendance)


def build_fixture_setup(
    repositories: Repositories,
    fixture: Fixture,
    engine: MatchdayEngine,
    today: dt.date,
    rng: WorldRng,
) -> tuple[MatchSetup, tuple[TeamInputs, TeamInputs]]:
    """The frozen setup of ``fixture`` and the two sides it came from; ``rng`` is the match's."""
    teams = (
        load_team(repositories, fixture.home_club_id),
        load_team(repositories, fixture.away_club_id),
    )
    weather = _weather(repositories, teams[0].club, today, engine, rng.fork("context"))
    context = MatchContext(
        fixture=fixture,
        weather=weather,
        referee_id=_referee(repositories, rng.fork("referee")),
        attendance=_crowd(teams[0], fixture, weather, engine, rng.fork("context")),
        today=today,
    )
    return build_match_setup(teams, context, engine.tables.setup), teams


def play_fixture(
    repositories: Repositories, fixture: Fixture, engine: MatchdayEngine, today: dt.date
) -> WorldDelta:
    """Play one fixture and write its delta through ``repositories``; returns the delta."""
    rng = WorldRng(derive_seed(engine.world_seed, f"match:{fixture.id}"))
    setup, teams = build_fixture_setup(repositories, fixture, engine, today, rng)
    result = engine.simulator.simulate(setup, rng.fork("simulate").seed % SEED_LIMIT)
    played = PlayedFixture(fixture, setup, result, teams, today)
    delta = derive_world_delta(played, engine.tables.post_match, rng.fork("after"))
    apply_delta(repositories, delta)
    return delta


def season_results(repositories: Repositories, season_id: SeasonId) -> list[MatchScore]:
    """The completed results of a season, as the standings need them."""
    matches = repositories.matches.find({"season_id": season_id, "status": COMPLETED})
    return [
        MatchScore(
            home_club_id=m.home_club_id,
            away_club_id=m.away_club_id,
            home_goals=m.home_goals or 0,
            away_goals=m.away_goals or 0,
        )
        for m in matches
    ]


def current_table(
    repositories: Repositories, season_id: SeasonId, clubs: Sequence[ClubId]
) -> tuple[StandingRow, ...]:
    """The table now, from completed matches."""
    return compute_table(season_id, clubs, season_results(repositories, season_id))


def snapshot_standings(
    repositories: Repositories, fixture: Fixture, clubs: Sequence[ClubId]
) -> StandingsSnapshot:
    """The table after the fixture's matchday, stored beside the matches."""
    rows = current_table(repositories, fixture.season_id, clubs)
    return StandingsSnapshot(
        season_id=fixture.season_id, after_matchday=fixture.matchday, rows=rows
    )
