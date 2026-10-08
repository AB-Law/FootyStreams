"""Club money: matchday takings, weekly wages and instalments, and season-end prize money.

Pure. Every function returns ``Posting`` rows; ``ledger.book`` writes them and moves balances.
Streams are sized so a typical club's revenue lands near its archetype income (gate ~30%,
hospitality ~5%, sponsors ~14%, broadcast 22%, merchandise ~8%, prize pool ~5%).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from footystreams.domain.club import Club
from footystreams.domain.finance import LedgerCategory
from footystreams.domain.manager import Manager
from footystreams.domain.player import Player, PlayerStatus
from footystreams.domain.staff import StaffMember
from footystreams.domain.types import ClubId, Money, PlayerId, Position
from footystreams.events.summary import PlayerMatchStats
from footystreams.league.config import FinanceConfig
from footystreams.league.ledger import Posting
from footystreams.league.outcome import Outcome


@dataclass(frozen=True, slots=True)
class WageBills:
    """What a club owes each week."""

    players: Money
    staff: Money


def wage_bills(
    players: Iterable[Player], staff: Iterable[StaffMember], manager: Manager | None
) -> WageBills:
    """Weekly wages of the active players under contract, and of staff and the manager."""
    player_wages = sum(
        p.contract.wage_weekly for p in players if p.contract and p.status is PlayerStatus.ACTIVE
    )
    staff_wages = sum(s.contract.wage_weekly for s in staff if s.contract)
    staff_wages += manager.contract.wage_weekly if manager and manager.contract else 0
    return WageBills(players=player_wages, staff=staff_wages)


def is_pay_day(today: dt.date, config: FinanceConfig) -> bool:
    """Weekly accruals fall on one weekday."""
    return today.weekday() == config.pay_weekday


def gate_income(attendance: int, club: Club, config: FinanceConfig) -> tuple[Money, Money]:
    """Ticket money and hospitality for a home match."""
    gate = round(attendance * club.stadium.ticket_price_base * config.ticket_price_scale)
    return gate, round(gate * config.hospitality_share_of_gate)


def _per_match_merchandise(club: Club, outcome: Outcome, config: FinanceConfig) -> Money:
    season_total = club.fanbase.size * config.merchandise_per_fan_per_season
    per_match = season_total * config.merchandise_form_weight / config.home_matches_per_season
    return round(per_match * config.merchandise_outcome_factor[outcome.value])


def matchday_postings(
    club: Club, match: tuple[str, int, Outcome], today: dt.date, config: FinanceConfig
) -> list[Posting]:
    """The home club's takings for a match: gate, hospitality and result-driven merchandise.

    ``match`` is (match id, attendance, the home side's outcome).
    """
    match_id, attendance, outcome = match
    gate, hospitality = gate_income(attendance, club, config)
    ref = {"match_id": match_id}
    return [
        Posting(club.id, today, LedgerCategory.MATCHDAY, gate, "gate", ref),
        Posting(club.id, today, LedgerCategory.MATCHDAY, hospitality, "hospitality", ref),
        Posting(
            club.id,
            today,
            LedgerCategory.MERCHANDISE,
            _per_match_merchandise(club, outcome, config),
            "matchday_merchandise",
            ref,
        ),
    ]


def _income_postings(club: Club, today: dt.date, config: FinanceConfig) -> list[Posting]:
    finances = club.finances
    sponsorship = sum(
        round(deal.annual_value / config.weeks_per_year)
        for deal in finances.sponsor_deals
        if deal.ends_on > today
    )
    broadcast = round(
        finances.broadcast_share * (1 - config.broadcast_merit_share) / config.weeks_per_year
    )
    merchandise = round(
        club.fanbase.size
        * config.merchandise_per_fan_per_season
        * (1 - config.merchandise_form_weight)
        / config.weeks_per_year
    )
    return [
        Posting(club.id, today, LedgerCategory.SPONSORSHIP, sponsorship, "sponsor_instalment"),
        Posting(club.id, today, LedgerCategory.BROADCAST, broadcast, "broadcast_instalment"),
        Posting(club.id, today, LedgerCategory.MERCHANDISE, merchandise, "weekly_merchandise"),
    ]


def _expense_postings(
    club: Club, bills: WageBills, today: dt.date, config: FinanceConfig
) -> list[Posting]:
    facilities = club.facilities
    upkeep = (facilities.training + facilities.youth + facilities.medical) * (
        config.facilities_upkeep_per_level_week
    )
    academy = club.academy.level * config.youth_academy_per_level_week
    interest = round(club.finances.debt * club.finances.debt_interest_rate / config.weeks_per_year)
    return [
        Posting(club.id, today, LedgerCategory.WAGES_PLAYERS, -bills.players, "player_wages"),
        Posting(club.id, today, LedgerCategory.WAGES_STAFF, -bills.staff, "staff_wages"),
        Posting(club.id, today, LedgerCategory.FACILITIES_UPKEEP, -upkeep, "facilities_upkeep"),
        Posting(club.id, today, LedgerCategory.YOUTH_ACADEMY, -academy, "academy_running_costs"),
        Posting(club.id, today, LedgerCategory.DEBT_SERVICE, -interest, "debt_interest"),
    ]


def weekly_postings(
    club: Club, bills: WageBills, today: dt.date, config: FinanceConfig
) -> list[Posting]:
    """One week of a club's instalments and running costs."""
    return [*_income_postings(club, today, config), *_expense_postings(club, bills, today, config)]


def apportion(total: Money, weights: Sequence[float]) -> list[Money]:
    """Split ``total`` in proportion to ``weights`` into whole crowns that sum exactly to it."""
    weight_sum = sum(weights)
    exact = [total * weight / weight_sum for weight in weights]
    shares = [int(value) for value in exact]
    leftover = total - sum(shares)
    by_remainder = sorted(range(len(exact)), key=lambda i: (-(exact[i] - shares[i]), i))
    for index in by_remainder[:leftover]:
        shares[index] += 1
    return shares


def season_end_postings(
    table: Sequence[ClubId], clubs: Sequence[Club], today: dt.date, config: FinanceConfig
) -> list[Posting]:
    """Prize money and broadcast merit by final position (``table`` is best first)."""
    by_id = {club.id: club for club in clubs}
    broadcast = sum(club.finances.broadcast_share for club in clubs)
    weights = [config.prize_position_decay**place for place in range(len(table))]
    prizes = apportion(round(broadcast * config.prize_pool_share_of_broadcast), weights)
    merit = apportion(round(broadcast * config.broadcast_merit_share), weights)
    return [
        posting
        for club_id, prize, share in zip(table, prizes, merit, strict=True)
        for posting in (
            Posting(by_id[club_id].id, today, LedgerCategory.PRIZE_MONEY, prize, "league_prize"),
            Posting(by_id[club_id].id, today, LedgerCategory.BROADCAST, share, "broadcast_merit"),
        )
    ]


CLEAN_SHEET_POSITIONS = frozenset(
    {Position.GK, Position.CB, Position.RB, Position.LB, Position.RWB, Position.LWB, Position.DM}
)


@dataclass(frozen=True, slots=True)
class MatchRef:
    """Which match, for which club, on which day."""

    match_id: str
    club_id: ClubId
    date: dt.date


def bonus_postings(
    squad: Sequence[Player],
    result: tuple[Mapping[PlayerId, PlayerMatchStats], int],
    ref: MatchRef,
) -> list[Posting]:
    """Appearance, goal and clean-sheet bonuses owed after a match, as one posting for the club.

    ``result`` is (the match's player stats, goals the club conceded).
    """
    stats, conceded = result
    owed = 0
    for player in squad:
        row = stats.get(PlayerId(player.id))
        if row is None or player.contract is None:
            continue
        owed += player.contract.appearance_bonus + row.goals * player.contract.goal_bonus
        if conceded == 0 and player.primary_position in CLEAN_SHEET_POSITIONS:
            owed += player.contract.clean_sheet_bonus
    posting = Posting(
        ref.club_id,
        ref.date,
        LedgerCategory.WAGES_PLAYERS,
        -owed,
        "match_bonuses",
        {"match_id": ref.match_id},
    )
    return [posting]
