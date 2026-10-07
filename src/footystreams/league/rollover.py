"""The season rollover: everything that happens between one season and the next.

Pure. ``rollover_season`` takes the loaded state of a finished season and returns one
``WorldDelta`` (applied in a single transaction). The steps follow docs/design/07 section 7:
awards, club year-end, contracts, retirements, progression, youth intake, squads, the next season.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from footystreams.domain.club import Club
from footystreams.domain.competition import Competition, Season
from footystreams.domain.ids import derive_id
from footystreams.domain.injury import Discipline
from footystreams.domain.mood import StateKind, StateModifier, WorldEvent
from footystreams.domain.player import Player, PlayerStatus
from footystreams.domain.prospects import ProspectFactory, ProspectRequest
from footystreams.domain.rng import WorldRng
from footystreams.domain.staff import StaffMember
from footystreams.domain.standings import StandingRow
from footystreams.domain.types import ClubId, PlayerId, Position, SeasonId
from footystreams.domain.valuation import market_value_of, wage_from_value
from footystreams.domain.world import SquadEntry
from footystreams.league.awards import SeasonTotals, award_modifiers, season_awards
from footystreams.league.club_year import (
    expected_places,
    performance,
    renew_sponsors,
    reset_budgets,
    update_standing,
)
from footystreams.league.delta import WorldDelta
from footystreams.league.development_config import RolloverConfig
from footystreams.league.progression import ProgressionInputs, progress_season
from footystreams.league.retirement import choose_retirements, retired, retirement_news
from footystreams.league.squad import (
    SquadContext,
    assign_numbers,
    rebalance,
    squad_entries,
    squad_value,
)
from footystreams.league.tables import LeagueTables
from footystreams.league.training import training_conditions
from footystreams.league.youth import contract_end, intake_requests, signed_prospect

FREE_AGENT_REPUTATION = 30
FULL_SEASON_MINUTES = 90
MIN_TERM_DAYS = 90
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


@dataclass(frozen=True, slots=True)
class RolloverServices:
    """Collaborators of the rollover."""

    tables: LeagueTables
    prospects: ProspectFactory


@dataclass(slots=True)
class _Work:
    """The evolving state while the steps run (local to one rollover call)."""

    players: dict[str, Player]
    clubs: dict[ClubId, Club]
    events: list[WorldEvent] = field(default_factory=list)
    modifiers: list[StateModifier] = field(default_factory=list)
    entries: list[SquadEntry] = field(default_factory=list)
    deletions: list[tuple[str, str]] = field(default_factory=list)


def _seniors_of(work: _Work, club_id: ClubId) -> list[Player]:
    return [
        p
        for p in work.players.values()
        if p.contract and p.contract.club_id == club_id and p.status is PlayerStatus.ACTIVE
    ]


def _awards(work: _Work, data: RolloverData, context: tuple[RolloverServices, dt.date]) -> None:
    services, today = context
    config = services.tables.development.rollover
    work.events.extend(
        season_awards(
            data.table, data.totals, (data.season.label, today, config.awards_min_appearances)
        )
    )
    champion = data.table[0].club_id
    winners: dict[StateKind, list[PlayerId]] = {
        StateKind.TROPHY_GLOW: [PlayerId(p.id) for p in _seniors_of(work, champion)]
    }
    individual = [
        e.participants[0].id
        for e in work.events
        if e.kind in {"top_scorer", "player_of_the_season"}
    ]
    winners[StateKind.AWARD_GLOW] = [PlayerId(pid) for pid in individual]
    work.modifiers.extend(award_modifiers(winners, today, services.tables.mood))


def _club_year_end(
    work: _Work, data: RolloverData, context: tuple[RolloverServices, dt.date], rng: WorldRng
) -> None:
    services, today = context
    config = services.tables.development.rollover
    expected = expected_places(list(data.clubs.values()))
    final = {row.club_id: row.position for row in data.table}
    count = len(data.clubs)
    for club_id in sorted(work.clubs):
        club = work.clubs[club_id]
        score = performance(expected[club_id], final[club_id], count)
        moved = update_standing(club, score, count, config)
        deals = renew_sponsors(
            moved,
            today,
            moved.club_reputation - club.club_reputation,
            (config, rng.fork(f"sponsors:{club_id}")),
        )
        moved = moved.model_copy(
            update={"finances": moved.finances.model_copy(update={"sponsor_deals": deals})}
        )
        work.clubs[club_id] = reset_budgets(moved, services.tables.config.finance, config)


def _wage_scale(work: _Work, club_id: ClubId, config: RolloverConfig) -> float:
    """Renewal wage scale: under 1.0 when the bill exceeds the budget, over 1.0 when well under it.

    A rich club pays its players more; the scale stays within the configured limits.
    """
    bill = sum(p.contract.wage_weekly for p in _seniors_of(work, club_id) if p.contract)
    allowed = work.clubs[club_id].finances.wage_budget_weekly * (1 + config.wage_tolerance)
    if not bill:
        return 1.0
    return max(MIN_WAGE_SCALE, min(config.wage_scale_max, allowed / bill))


def renew_contract(player: Player, today: dt.date, years: int, scale: float) -> Player:
    """A new contract for a player whose deal is about to end: half old wage, half market wage."""
    contract = player.contract
    if contract is None:
        return player
    target = wage_from_value(market_value_of(player, today))
    wage = round((0.5 * contract.wage_weekly + 0.5 * target) * scale)
    renewed = contract.model_copy(
        update={"start": today, "end": contract_end(today, years), "wage_weekly": wage}
    )
    return player.model_copy(update={"contract": renewed})


def _renew_contracts(work: _Work, context: tuple[RolloverServices, dt.date], rng: WorldRng) -> None:
    services, today = context
    config = services.tables.development.rollover
    for club_id in sorted(work.clubs):
        scale = _wage_scale(work, club_id, config)
        expiring = [
            p
            for p in _seniors_of(work, club_id)
            if p.contract and (p.contract.end - today).days < MIN_TERM_DAYS
        ]
        for player in sorted(expiring, key=lambda p: p.id):
            years = rng.fork(f"renew:{player.id}").randint(*config.contract_extend_years)
            work.players[player.id] = renew_contract(player, today, years, scale)


def _retire(work: _Work, context: tuple[RolloverServices, dt.date], rng: WorldRng) -> None:
    services, today = context
    config = services.tables.development.retirement
    chosen = choose_retirements(list(work.players.values()), today, config, rng)
    for player in chosen:
        work.players[player.id] = retired(player, today)
        work.events.append(retirement_news(player, today))


def _playing_time(
    totals: Mapping[PlayerId, SeasonTotals], player: Player, played: int, full: float
) -> float:
    minutes = totals.get(PlayerId(player.id), SeasonTotals()).minutes
    return min(1.0, minutes / (played * FULL_SEASON_MINUTES * full)) if played else 0.0


def _progress(
    work: _Work, data: RolloverData, context: tuple[RolloverServices, dt.date], rng: WorldRng
) -> None:
    services, today = context
    development = services.tables.development
    inputs = ProgressionInputs(development, services.tables.roles, today)
    played = {row.club_id: row.played for row in data.table}
    pull = development.rollover
    for pid in sorted(work.players):
        player = work.players[pid]
        if player.status is PlayerStatus.RETIRED:
            continue
        club_id = player.contract.club_id if player.contract else None
        club = work.clubs.get(club_id) if club_id else None
        fraction = development.progression.full_playing_time_minutes
        share = _playing_time(
            data.totals, player, played.get(club_id, 0) if club_id else 0, fraction
        )
        conditions = training_conditions(
            club, data.staff.get(club_id, ()) if club_id else (), share, development.progression
        )
        grown, _ = progress_season(player, conditions, inputs, rng.fork(player.id))
        target = pull.player_reputation_ability_weight * grown.ability_current + (
            1 - pull.player_reputation_ability_weight
        ) * (club.club_reputation if club else FREE_AGENT_REPUTATION)
        reputation = round(
            grown.reputation + pull.player_reputation_pull * (target - grown.reputation)
        )
        work.players[pid] = grown.model_copy(
            update={"reputation": max(0, min(100, reputation)), "discipline": Discipline()}
        )


def _mean_ability(players: Sequence[Player]) -> float:
    seniors = [
        p.ability_current for p in players if not p.is_youth and p.status is PlayerStatus.ACTIVE
    ]
    return sum(seniors) / len(seniors) if seniors else 0.0


def _formation_positions(tables: LeagueTables, club: Club) -> list[Position]:
    return list(tables.formations.formations[club.default_tactics.formation].positions())


def _create(
    work: _Work,
    data: RolloverData,
    requests: Sequence[ProspectRequest],
    context: tuple[RolloverServices, WorldRng],
) -> list[Player]:
    services, rng = context
    known = [*work.players.values(), *data.retired_names]
    return services.prospects.create(requests, known, rng)


def _intake(
    work: _Work,
    data: RolloverData,
    context: tuple[RolloverServices, dt.date],
    rng: WorldRng,
) -> None:
    """The academy intake of every club, signed on youth contracts."""
    services, today = context
    youth = services.tables.development.youth
    mean = _mean_ability(data.players)
    key = str(data.season.starts_on.year + 1)
    requests: list[ProspectRequest] = []
    for club_id in sorted(work.clubs):
        club = work.clubs[club_id]
        shape = (_formation_positions(services.tables, club), mean)
        requests.extend(intake_requests(club, shape, key, youth, rng.fork(f"intake:{club_id}")))
    for request, player in zip(
        requests, _create(work, data, requests, (services, rng.fork("create"))), strict=True
    ):
        if request.club_id is not None:
            work.players[player.id] = signed_prospect(player, request.club_id, today, youth)


def _top_up_pool(
    work: _Work, data: RolloverData, context: tuple[RolloverServices, dt.date], rng: WorldRng
) -> None:
    """Journeymen join the free-agent pool until it has the configured size."""
    services, _ = context
    config = services.tables.development.squad
    free = sum(1 for p in work.players.values() if p.status is PlayerStatus.FREE_AGENT)
    missing = max(0, config.free_agent_pool - free)
    positions = [Position.GK, Position.CB, Position.RB, Position.CM, Position.RW, Position.ST]
    mean = _mean_ability(data.players)
    key = f"pool:{data.season.starts_on.year + 1}"
    requests = [
        ProspectRequest(
            key=f"{key}:{index}",
            position=positions[index % len(positions)],
            age=rng.fork(f"age:{index}").randint(*config.journeyman_age),
            ability=round(mean * config.journeyman_ability_fraction),
            potential_bonus=0,
            region=next(iter(work.clubs.values())).location.region,
            club_reputation=FREE_AGENT_REPUTATION,
            club_id=None,
            youth=False,
        )
        for index in range(missing)
    ]
    for player in _create(work, data, requests, (services, rng.fork("create"))):
        work.players[player.id] = player


def _trim_pool(work: _Work, context: tuple[RolloverServices, dt.date]) -> None:
    """The weakest unsigned players beyond the pool limit leave the game."""
    services, today = context
    limit = services.tables.development.squad.free_agent_pool_max
    weight = services.tables.development.youth.potential_weight
    free = sorted(
        (p for p in work.players.values() if p.status is PlayerStatus.FREE_AGENT),
        key=lambda p: (-squad_value(p, weight), p.id),
    )
    for player in free[limit:]:
        work.players[player.id] = retired(player, today)
        work.events.append(retirement_news(player, today))


def _squads(work: _Work, data: RolloverData, context: tuple[RolloverServices, dt.date]) -> None:
    """Rebalance every club's squad, then number the newcomers and sync the squad entries."""
    services, today = context
    squad_context = SquadContext(
        today, services.tables.development.squad, services.tables.development.youth
    )
    for club_id in sorted(work.clubs):
        pool = sorted(
            (p for p in work.players.values() if p.status is PlayerStatus.FREE_AGENT),
            key=lambda p: p.id,
        )
        members = _seniors_of(work, club_id)
        moves = rebalance(club_id, members, pool, squad_context)
        for player in (*moves.promoted, *moves.signed, *moves.released):
            work.players[player.id] = player
        final = assign_numbers(_seniors_of(work, club_id))
        for player in final:
            work.players[player.id] = player
        wanted, stale = squad_entries(club_id, final, data.entries.get(club_id, ()))
        work.entries.extend(wanted)
        work.deletions.extend(("squad_entries", key) for key in stale)


def next_season(season: Season, competition: Competition, tables: LeagueTables) -> Season:
    """The season after ``season``: next year's label and dates, the same matchdays."""
    year = season.starts_on.year + 1
    calendar = tables.config.calendar
    label = f"{year}/{str(year + 1)[-2:]}"
    return Season(
        id=SeasonId(derive_id("season", competition.id, label)),
        competition_id=competition.id,
        label=label,
        starts_on=calendar.season_start_in(year),
        ends_on=calendar.season_end_in(year),
        matchdays=season.matchdays,
    )


def rollover_season(
    data: RolloverData, services: RolloverServices, today: dt.date, rng: WorldRng
) -> WorldDelta:
    """Run every rollover step for a finished season and return what changed."""
    work = _Work(players={p.id: p for p in data.players}, clubs=dict(data.clubs))
    context = (services, today)
    _awards(work, data, context)
    _club_year_end(work, data, context, rng.fork("clubs"))
    _retire(work, context, rng.fork("retire"))
    _renew_contracts(work, context, rng.fork("contracts"))
    _progress(work, data, context, rng.fork("progress"))
    _intake(work, data, context, rng.fork("intake"))
    _top_up_pool(work, data, context, rng.fork("pool"))
    _squads(work, data, context)
    _trim_pool(work, context)
    changed = tuple(p for pid, p in sorted(work.players.items()) if p is not _original(data, pid))
    return WorldDelta(
        players=changed,
        clubs=tuple(work.clubs[cid] for cid in sorted(work.clubs)),
        modifiers=tuple(work.modifiers),
        world_events=tuple(work.events),
        seasons=(next_season(data.season, data.competition, services.tables),),
        squad_entries=tuple(work.entries),
        deletions=tuple(work.deletions),
    )


def _original(data: RolloverData, player_id: str) -> Player | None:
    return next((p for p in data.players if p.id == player_id), None)
