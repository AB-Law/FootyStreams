"""``DailyTick``: advance the world one day through the ordered stages, then play the fixtures.

Every stage and every match is its own transaction. A stage writes a ``world_log`` row
``(date, stage, delta_hash)``; running a day again skips what the log shows as done, so a crash
between stages resumes without repeating or losing anything (docs/design/07 section 2).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.domain.fixture import Fixture
from footystreams.domain.prospects import ProspectFactory
from footystreams.domain.rng import WorldRng, derive_seed
from footystreams.league.clock import WorldClock
from footystreams.league.delta import apply_delta
from footystreams.league.matchday import (
    MatchdayEngine,
    due_fixtures,
    play_fixture,
    snapshot_standings,
)
from footystreams.league.rollover_state import RolloverServices
from footystreams.league.stages import (
    ClubAdminStage,
    ContractExpiryStage,
    LifeEventsStage,
    RecoveryStage,
    RolloverStage,
    SeasonEndStage,
    Stage,
    TrainingStage,
    TransferStage,
)
from footystreams.persistence.ports import StageLogEntry, UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class DayReport:
    """What one day did."""

    date: dt.date
    stages_run: tuple[str, ...]
    matches_played: int


def default_stages(engine: MatchdayEngine, prospects: ProspectFactory | None = None) -> list[Stage]:
    """The stages in the order of docs/design/07 section 2.

    The off-season rollover needs a prospect factory (it creates academy players); without one
    the world simply stops at the end of the season.
    """
    tables = engine.tables
    stages: list[Stage] = [
        RecoveryStage(tables),
        TrainingStage(tables),
        LifeEventsStage(tables),
        ClubAdminStage(tables),
        SeasonEndStage(tables),
        ContractExpiryStage(tables),
    ]
    if prospects is not None:
        services = RolloverServices(tables, prospects)
        stages.extend([TransferStage(services), RolloverStage(services)])
    return stages


class DailyTick:
    """Runs the world one day at a time."""

    def __init__(
        self,
        factory: UnitOfWorkFactory,
        engine: MatchdayEngine,
        stages: Sequence[Stage] | None = None,
    ) -> None:
        """Create a tick over a database; ``stages`` defaults to this milestone's pipeline."""
        self._factory = factory
        self._engine = engine
        self._stages = list(stages) if stages is not None else default_stages(engine)
        self._clock = WorldClock(factory)

    def run_day(self) -> DayReport:
        """Run today's stages, play today's fixtures, then move the clock to tomorrow."""
        today = self._clock.current_date()
        ran = [stage.name for stage in self._stages if self._run_stage(stage, today)]
        played = self._play_matchday(today)
        self._clock.advance_day()
        return DayReport(today, tuple(ran), played)

    def _run_stage(self, stage: Stage, today: dt.date) -> bool:
        """Run one stage in its own transaction unless the log says it already ran."""
        key = f"{today.isoformat()}:{stage.name}"
        with self._factory() as uow:
            if uow.stage_log.get(key) is not None:
                return False
            rng = WorldRng(derive_seed(self._engine.world_seed, f"stage:{key}"))
            delta = stage.run(uow, today, rng)
            apply_delta(uow, delta)
            uow.stage_log.save(
                StageLogEntry(date=today, stage=stage.name, delta_hash=delta.content_hash())
            )
            uow.commit()
        return True

    def _play_matchday(self, today: dt.date) -> int:
        """Play every fixture due today (one transaction each), then close the matchday."""
        with self._factory() as uow:
            fixtures = due_fixtures(uow, today)
        for fixture in fixtures:
            with self._factory() as uow:
                play_fixture(uow, fixture, self._engine, today)
                uow.commit()
        if fixtures:
            self._close_matchday(fixtures[0])
        return len(fixtures)

    def _close_matchday(self, fixture: Fixture) -> None:
        """Store the table once the whole matchday has been played."""
        with self._factory() as uow:
            pending = uow.fixtures.find(
                {
                    "season_id": fixture.season_id,
                    "matchday": fixture.matchday,
                    "status": "scheduled",
                }
            )
            if pending:
                return
            clubs = uow.competitions.require(fixture.competition_id).club_ids
            uow.standings.save(snapshot_standings(uow, fixture, clubs))
            uow.commit()
