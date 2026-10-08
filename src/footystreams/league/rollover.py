"""The season rollover: everything that happens between one season and the next.

Pure. ``rollover_season`` takes the loaded state of a finished season and returns one
``WorldDelta`` (applied in a single transaction). The steps follow docs/design/07 section 7:
awards, club year-end, contracts, retirements, progression, youth intake, squads, the next season.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping

from footystreams.domain.competition import Competition, Season
from footystreams.domain.ids import derive_id
from footystreams.domain.injury import Discipline
from footystreams.domain.mood import StateKind
from footystreams.domain.player import Player, PlayerStatus
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import PlayerId, SeasonId
from footystreams.domain.valuation import market_value_of, wage_from_value
from footystreams.league.awards import SeasonTotals, award_modifiers, season_awards
from footystreams.league.club_year import (
    expected_places,
    performance,
    renew_sponsors,
    reset_budgets,
    update_standing,
)
from footystreams.league.delta import WorldDelta
from footystreams.league.progression import ProgressionInputs, progress_season
from footystreams.league.retirement import choose_retirements, retired, retirement_news
from footystreams.league.rollover_squads import intake, mean_ability, squads, top_up_pool, trim_pool
from footystreams.league.rollover_state import (
    KEY_REFERENCE_ABILITY,
    RolloverData,
    RolloverServices,
    Work,
    seniors_of,
    wage_scale,
)
from footystreams.league.tables import LeagueTables
from footystreams.league.training import training_conditions
from footystreams.league.youth import contract_end
from footystreams.persistence.ports import MetaEntry

FREE_AGENT_REPUTATION = 30
FULL_SEASON_MINUTES = 90
MIN_TERM_DAYS = 90


def _awards(work: Work, data: RolloverData, context: tuple[RolloverServices, dt.date]) -> None:
    services, today = context
    config = services.tables.development.rollover
    work.events.extend(
        season_awards(
            data.table, data.totals, (data.season.label, today, config.awards_min_appearances)
        )
    )
    champion = data.table[0].club_id
    winners: dict[StateKind, list[PlayerId]] = {
        StateKind.TROPHY_GLOW: [PlayerId(p.id) for p in seniors_of(work, champion)]
    }
    individual = [
        e.participants[0].id
        for e in work.events
        if e.kind in {"top_scorer", "player_of_the_season"}
    ]
    winners[StateKind.AWARD_GLOW] = [PlayerId(pid) for pid in individual]
    work.modifiers.extend(award_modifiers(winners, today, services.tables.mood))


def _club_year_end(
    work: Work, data: RolloverData, context: tuple[RolloverServices, dt.date], rng: WorldRng
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


def _renew_contracts(work: Work, context: tuple[RolloverServices, dt.date], rng: WorldRng) -> None:
    services, today = context
    config = services.tables.development.rollover
    for club_id in sorted(work.clubs):
        scale = wage_scale(work, club_id, config)
        expiring = [
            p
            for p in seniors_of(work, club_id)
            if p.contract and (p.contract.end - today).days < MIN_TERM_DAYS
        ]
        for player in sorted(expiring, key=lambda p: p.id):
            years = rng.fork(f"renew:{player.id}").randint(*config.contract_extend_years)
            work.players[player.id] = renew_contract(player, today, years, scale)


def _retire(work: Work, context: tuple[RolloverServices, dt.date], rng: WorldRng) -> None:
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
    work: Work, data: RolloverData, context: tuple[RolloverServices, dt.date], rng: WorldRng
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
    reference = (
        data.reference_ability if data.reference_ability is not None else mean_ability(data.players)
    )
    work = Work(
        players={p.id: p for p in data.players}, clubs=dict(data.clubs), reference=reference
    )
    context = (services, today)
    _awards(work, data, context)
    _club_year_end(work, data, context, rng.fork("clubs"))
    _retire(work, context, rng.fork("retire"))
    _renew_contracts(work, context, rng.fork("contracts"))
    _progress(work, data, context, rng.fork("progress"))
    intake(work, data, context, rng.fork("intake"))
    top_up_pool(work, data, context, rng.fork("pool"))
    squads(work, data, context)
    trim_pool(work, context)
    changed = tuple(p for pid, p in sorted(work.players.items()) if p is not _original(data, pid))
    return WorldDelta(
        players=changed,
        clubs=tuple(work.clubs[cid] for cid in sorted(work.clubs)),
        modifiers=tuple(work.modifiers),
        world_events=tuple(work.events),
        seasons=(next_season(data.season, data.competition, services.tables),),
        squad_entries=tuple(work.entries),
        meta=(
            ()
            if data.reference_ability is not None
            else (MetaEntry(key=KEY_REFERENCE_ABILITY, value=f"{reference:.4f}"),)
        ),
        deletions=tuple(work.deletions),
    )


def _original(data: RolloverData, player_id: str) -> Player | None:
    return next((p for p in data.players if p.id == player_id), None)
