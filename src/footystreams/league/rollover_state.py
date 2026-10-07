"""The shared state and inputs of the season rollover steps."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from footystreams.domain.club import Club
from footystreams.domain.competition import Competition, Season
from footystreams.domain.mood import StateModifier, WorldEvent
from footystreams.domain.player import Player, PlayerStatus
from footystreams.domain.prospects import ProspectFactory
from footystreams.domain.staff import StaffMember
from footystreams.domain.standings import StandingRow
from footystreams.domain.types import ClubId, PlayerId
from footystreams.domain.world import SquadEntry
from footystreams.league.awards import SeasonTotals
from footystreams.league.development_config import RolloverConfig
from footystreams.league.tables import LeagueTables

KEY_REFERENCE_ABILITY = "reference_ability"
MIN_WAGE_SCALE = 0.5


@dataclass(frozen=True, slots=True)
class RolloverData:
    """The loaded state of a season that has just ended."""

    season: Season
    competition: Competition
    clubs: Mapping[ClubId, Club]
    players: Sequence[Player]  # active players and free agents
    staff: Mapping[ClubId, Sequence[StaffMember]]
    entries: Mapping[ClubId, Sequence[SquadEntry]]
    table: Sequence[StandingRow]
    totals: Mapping[PlayerId, SeasonTotals]
    retired_names: Sequence[Player]  # retired players, only so new names avoid theirs
    reference_ability: float | None  # the league level recorded at the first rollover


@dataclass(frozen=True, slots=True)
class RolloverServices:
    """Collaborators of the rollover."""

    tables: LeagueTables
    prospects: ProspectFactory


@dataclass(slots=True)
class Work:
    """The evolving state while the steps run (local to one rollover call)."""

    players: dict[str, Player]
    clubs: dict[ClubId, Club]
    reference: float
    events: list[WorldEvent] = field(default_factory=list)
    modifiers: list[StateModifier] = field(default_factory=list)
    entries: list[SquadEntry] = field(default_factory=list)
    deletions: list[tuple[str, str]] = field(default_factory=list)


def seniors_of(work: Work, club_id: ClubId) -> list[Player]:
    """The club's active players under contract (prospects included)."""
    return [
        p
        for p in work.players.values()
        if p.contract and p.contract.club_id == club_id and p.status is PlayerStatus.ACTIVE
    ]


def wage_scale(work: Work, club_id: ClubId, config: RolloverConfig) -> float:
    """Renewal wage scale: under 1.0 when the bill exceeds the budget, over 1.0 when well under it.

    A rich club pays its players more; the scale stays within the configured limits.
    """
    bill = sum(p.contract.wage_weekly for p in seniors_of(work, club_id) if p.contract)
    allowed = work.clubs[club_id].finances.wage_budget_weekly * (1 + config.wage_tolerance)
    if not bill:
        return 1.0
    return max(MIN_WAGE_SCALE, min(config.wage_scale_max, allowed / bill))
