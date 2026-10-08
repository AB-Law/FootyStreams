"""Rows that exist only in persistence: key/value metadata, stage log, summaries, snapshots."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

from footystreams.domain.standings import StandingRow
from footystreams.domain.types import MatchId, SeasonId
from footystreams.events.summary import MatchSummary
from footystreams.events.types import MatchEvent


class StoredRecord(BaseModel):
    """Frozen, strict base of the persistence-only records."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class MetaEntry(StoredRecord):
    """One world_meta key/value (seed, current in-world date, versions, config hash)."""

    key: str = Field(min_length=1, max_length=80)
    value: str


class StageLogEntry(StoredRecord):
    """world_log: a daily-tick stage ran for a date; the delta hash makes re-runs verifiable."""

    date: dt.date
    stage: str = Field(min_length=1, max_length=40)
    delta_hash: str = Field(min_length=1, max_length=128)


class SummaryRecord(StoredRecord):
    """The match summary stored beside its match."""

    match_id: MatchId
    summary: MatchSummary


class StandingsSnapshot(StoredRecord):
    """The table after a matchday, as computed then."""

    season_id: SeasonId
    after_matchday: int = Field(ge=0)
    rows: tuple[StandingRow, ...]


class StoredEvent(StoredRecord):
    """One match event with the columns the log is queried by (append-only ground truth)."""

    match_id: MatchId
    seq: int = Field(ge=0)
    type: str
    tick: int = Field(ge=0)
    event: MatchEvent
