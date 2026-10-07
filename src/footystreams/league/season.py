"""``SeasonRunner``: schedule a season, then run the days until it ends."""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.competition import Competition, Season
from footystreams.domain.fixture import Fixture
from footystreams.domain.rng import WorldRng, derive_seed
from footystreams.domain.standings import StandingRow
from footystreams.domain.types import ClubId
from footystreams.league.calendar import matchday_dates
from footystreams.league.clock import WorldClock
from footystreams.league.daily import DailyTick, DayReport
from footystreams.league.delta import WorldDelta, apply_delta
from footystreams.league.matchday import MatchdayEngine, current_table
from footystreams.league.schedule import ScheduleError, build_rounds, schedule_fixtures
from footystreams.persistence.ports import Repositories, UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class SeasonResult:
    """How a season ended."""

    season: Season
    table: tuple[StandingRow, ...]
    matches_played: int


def derby_pairs(repositories: Repositories, club_ids: tuple[ClubId, ...]) -> set[frozenset[ClubId]]:
    """Pairs of clubs in the competition that are derby rivals."""
    members = set(club_ids)
    pairs: set[frozenset[ClubId]] = set()
    for club_id in club_ids:
        for rivalry in repositories.clubs.require(club_id).rivalries:
            if rivalry.is_derby and rivalry.club_id in members:
                pairs.add(frozenset((club_id, rivalry.club_id)))
    return pairs


class SeasonRunner:
    """Prepares the fixtures of a season and drives the daily tick through it."""

    def __init__(self, factory: UnitOfWorkFactory, engine: MatchdayEngine) -> None:
        """Create a runner over a database and the matchday engine."""
        self._factory = factory
        self._engine = engine
        self._tick = DailyTick(factory, engine)
        self._clock = WorldClock(factory)

    def prepare(self, season: Season) -> int:
        """Schedule the season's fixtures if there are none yet; returns how many exist."""
        with self._factory() as uow:
            existing = uow.fixtures.count({"season_id": season.id})
            if existing:
                return existing
            competition = uow.competitions.require(season.competition_id)
            fixtures = self._schedule(uow, season, competition)
            apply_delta(uow, WorldDelta(fixtures=tuple(fixtures)))
            uow.commit()
        return len(fixtures)

    def _schedule(
        self, uow: Repositories, season: Season, competition: Competition
    ) -> list[Fixture]:
        rng = WorldRng(derive_seed(self._engine.world_seed, f"schedule:{season.id}"))
        derbies = derby_pairs(uow, competition.club_ids)
        rounds = build_rounds(competition.club_ids, rng, derbies)
        dates = matchday_dates(self._engine.tables.config.calendar, season.starts_on, len(rounds))
        if dates[-1] > season.ends_on:
            msg = f"{len(rounds)} matchdays do not fit in {season.starts_on}..{season.ends_on}"
            raise ScheduleError(msg)
        return schedule_fixtures(rounds, (competition.id, season.id), dates, derbies)

    def run_season(self, season: Season) -> SeasonResult:
        """Prepare the season, run every day up to and including its last, return the result."""
        self.prepare(season)
        played = 0
        while self._clock.current_date() <= season.ends_on:
            played += self._tick.run_day().matches_played
        return self.result(season, played)

    def run_day(self) -> DayReport:
        """One day of the world (for ``--matchday`` style stepping)."""
        return self._tick.run_day()

    def result(self, season: Season, matches_played: int) -> SeasonResult:
        """The table as it stands."""
        with self._factory() as uow:
            clubs = uow.competitions.require(season.competition_id).club_ids
            table = current_table(uow, season.id, clubs)
        return SeasonResult(season, table, matches_played)
