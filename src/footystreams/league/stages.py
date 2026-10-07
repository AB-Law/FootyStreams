"""Daily tick stages that run before the matches (docs/design/07 section 2).

Each stage reads the repositories it is given and returns a ``WorldDelta``; it never writes. The
tick applies the delta and logs it. Stages that belong to later milestones (training, contracts,
transfers) are added to the list in ``daily`` when they exist.
"""

from __future__ import annotations

import datetime as dt
from typing import ClassVar, Protocol

from footystreams.domain.club import Club
from footystreams.domain.competition import Season
from footystreams.domain.fixture import FixtureStatus
from footystreams.domain.mood import StateModifier
from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import PlayerId
from footystreams.league.delta import WorldDelta, merge_all
from footystreams.league.finance import (
    WageBills,
    is_pay_day,
    season_end_postings,
    wage_bills,
    weekly_postings,
)
from footystreams.league.ledger import book
from footystreams.league.matchday import current_table
from footystreams.league.mood_rules import modifier_for_return
from footystreams.league.progression import ProgressionInputs, micro_step
from footystreams.league.recovery import decay_sharpness, recover
from footystreams.league.rollover import rollover_season
from footystreams.league.rollover_data import load_rollover_data
from footystreams.league.rollover_state import RolloverServices
from footystreams.league.tables import LeagueTables
from footystreams.league.training import training_conditions
from footystreams.league.world_events import generate_life_events
from footystreams.persistence.ports import Repositories

ACTIVE = "active"
PLAYED = FixtureStatus.PLAYED.value
RECENT_MATCH_DAYS = 6  # fatigue and morale from a match are gone within this many days


class Stage(Protocol):
    """One step of the daily tick."""

    name: ClassVar[str]

    def run(self, repositories: Repositories, today: dt.date, rng: WorldRng) -> WorldDelta:
        """What this stage changes today."""


class RecoveryStage:
    """Fatigue, fitness, morale, weekly sharpness decay, injury healing and the joy of returning.

    On pay day everyone is looked at; on other days only players who can still be recovering:
    the injured and the squads that played in the last few days. That keeps the daily tick cheap
    without changing the outcome (a rested player is unchanged by ``recover``).
    """

    name: ClassVar[str] = "recovery"

    def __init__(self, tables: LeagueTables) -> None:
        """Create the stage over the league tables."""
        self._tables = tables

    def run(self, repositories: Repositories, today: dt.date, rng: WorldRng) -> WorldDelta:  # noqa: ARG002
        """Recover the players due a look; only players who changed are written."""
        config = self._tables.config.recovery
        weekly = is_pay_day(today, self._tables.config.finance)
        changed: list[Player] = []
        modifiers: list[StateModifier] = []
        for player in self._candidates(repositories, today, weekly=weekly):
            updated = recover(player, today, config)
            if weekly:
                updated = decay_sharpness(updated, config)
            if player.current_injury is not None and updated.current_injury is None:
                joy = modifier_for_return(
                    PlayerId(player.id), player.current_injury, today, self._tables.mood
                )
                modifiers.extend([joy] if joy else [])
            if updated is not player:
                changed.append(updated)
        return WorldDelta(players=tuple(changed), modifiers=tuple(modifiers))

    @staticmethod
    def _candidates(repositories: Repositories, today: dt.date, *, weekly: bool) -> list[Player]:
        if weekly:
            return repositories.players.find({"status": ACTIVE})
        found = {p.id: p for p in repositories.players.find({"status": ACTIVE, "injured": True})}
        for days_ago in range(1, RECENT_MATCH_DAYS + 1):
            day = today - dt.timedelta(days=days_ago)
            for fixture in repositories.fixtures.find({"date": day, "status": PLAYED}):
                for club_id in (fixture.home_club_id, fixture.away_club_id):
                    for player in repositories.players.find({"club_id": club_id, "status": ACTIVE}):
                        found[player.id] = player
        return [found[key] for key in sorted(found)]


class LifeEventsStage:
    """Seeded life events around the players: media stories, rows, personal matters.

    Rolled once a week (on pay day) with the chance of at least one event in the week, so the
    daily tick does not load every player every day.
    """

    name: ClassVar[str] = "life_events"

    def __init__(self, tables: LeagueTables) -> None:
        """Create the stage over the league tables."""
        self._tables = tables

    def run(self, repositories: Repositories, today: dt.date, rng: WorldRng) -> WorldDelta:
        """Roll the week's events for every contracted player; nothing on other days."""
        if not is_pay_day(today, self._tables.config.finance):
            return WorldDelta()
        players = repositories.players.find({"status": ACTIVE})
        configs = (self._tables.config.world_events, self._tables.mood)
        return generate_life_events(players, today, rng, configs)


class ClubAdminStage:
    """Weekly wages, instalments, running costs and interest, on pay day."""

    name: ClassVar[str] = "club_admin"

    def __init__(self, tables: LeagueTables) -> None:
        """Create the stage over the league tables."""
        self._tables = tables

    def run(self, repositories: Repositories, today: dt.date, rng: WorldRng) -> WorldDelta:  # noqa: ARG002
        """One week of every club's money; nothing on other days."""
        config = self._tables.config.finance
        if not is_pay_day(today, config):
            return WorldDelta()
        clubs = repositories.clubs.all()
        postings = [
            posting
            for club in clubs
            for posting in weekly_postings(club, self._bills(repositories, club), today, config)
        ]
        return book({club.id: club for club in clubs}, postings)

    @staticmethod
    def _bills(repositories: Repositories, club: Club) -> WageBills:
        players = repositories.players.find({"club_id": club.id, "status": ACTIVE})
        staff = repositories.staff.find({"club_id": club.id})
        managers = repositories.managers.find({"club_id": club.id})
        return wage_bills(players, staff, managers[0] if managers else None)


class SeasonEndStage:
    """Prize money and broadcast merit by final position, on the day a season ends."""

    name: ClassVar[str] = "season_end"

    def __init__(self, tables: LeagueTables) -> None:
        """Create the stage over the league tables."""
        self._tables = tables

    def run(self, repositories: Repositories, today: dt.date, rng: WorldRng) -> WorldDelta:  # noqa: ARG002
        """Pay the final table of every season that ends today."""
        deltas = [
            self._pay(repositories, season, today)
            for season in repositories.seasons.all()
            if season.ends_on == today
        ]
        return merge_all(deltas)

    def _pay(self, repositories: Repositories, season: Season, today: dt.date) -> WorldDelta:
        competition = repositories.competitions.require(season.competition_id)
        table = current_table(repositories, season.id, competition.club_ids)
        clubs = [repositories.clubs.require(club_id) for club_id in competition.club_ids]
        postings = season_end_postings(
            [row.club_id for row in table], clubs, today, self._tables.config.finance
        )
        return book({club.id: club for club in clubs}, postings)


class TrainingStage:
    """Weekly training: a few single-point gains for players who still have room to grow."""

    name: ClassVar[str] = "training"

    def __init__(self, tables: LeagueTables) -> None:
        """Create the stage over the league tables."""
        self._tables = tables

    def run(self, repositories: Repositories, today: dt.date, rng: WorldRng) -> WorldDelta:
        """Train every active player on pay day; nothing on other days."""
        if not is_pay_day(today, self._tables.config.finance):
            return WorldDelta()
        inputs = ProgressionInputs(self._tables.development, self._tables.roles, today)
        changed: list[Player] = []
        for club in repositories.clubs.all():
            staff = repositories.staff.find({"club_id": club.id})
            conditions = training_conditions(
                club,
                staff,
                inputs.config.progression.default_playing_time,
                inputs.config.progression,
            )
            for player in repositories.players.find({"club_id": club.id, "status": ACTIVE}):
                trained, _ = micro_step(player, conditions, inputs, rng.fork(player.id))
                if trained is not player:
                    changed.append(trained)
        return WorldDelta(players=tuple(changed))


class RolloverStage:
    """The off-season: awards, year-end, retirements, progression, intake, squads, next season."""

    name: ClassVar[str] = "rollover"

    def __init__(self, services: RolloverServices) -> None:
        """Create the stage over the league tables and the prospect factory."""
        self._services = services

    def run(self, repositories: Repositories, today: dt.date, rng: WorldRng) -> WorldDelta:
        """Roll over every season that ended yesterday and has no successor yet."""
        yesterday = today - dt.timedelta(days=1)
        deltas = [
            rollover_season(
                load_rollover_data(repositories, season), self._services, today, rng.fork(season.id)
            )
            for season in repositories.seasons.all()
            if season.ends_on == yesterday
        ]
        return merge_all(deltas)
