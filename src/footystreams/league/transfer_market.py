"""The market's working state and the completion of a deal.

While a window day runs, deals change who plays where and how much money each club has, and the
next deal of the day must see that. ``Market`` is that local, mutable state; ``complete`` is the
one place a deal is carried out, so the contract, the squad, the two ledger legs, the records and
the news always change together. The day's result leaves as a single ``WorldDelta`` (one
transaction), which is what makes a transfer atomic.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from footystreams.domain.club import Club
from footystreams.domain.contract import Contract, SquadRole
from footystreams.domain.finance import LedgerCategory
from footystreams.domain.ids import derive_id
from footystreams.domain.manager import Manager
from footystreams.domain.mood import (
    ModifierSource,
    ModifierVisibility,
    StateKind,
    StateModifier,
    WorldEvent,
)
from footystreams.domain.player import Player, PlayerStatus, SquadStatus
from footystreams.domain.staff import StaffMember
from footystreams.domain.transfer import (
    OUTSIDE_WORLD,
    ContractOffer,
    Transfer,
    TransferBid,
    TransferListing,
    TransferWindow,
)
from footystreams.domain.types import ClubId, EntityKind, EntityRef, Id, Money, PlayerId
from footystreams.domain.world import SquadEntry
from footystreams.league.contracts import Agreed
from footystreams.league.ledger import Posting
from footystreams.league.modifiers import ModifierSpec, new_modifier
from footystreams.league.mood_config import MoodConfig
from footystreams.league.youth import contract_end

KEY_RANK = 7  # the seven best players of a squad are its key players
SIGNING_ENTHUSIASM = 0.6


@dataclass(slots=True)
class Market:
    """Everything a window day reads and writes."""

    window: TransferWindow
    today: dt.date
    players: dict[str, Player]
    clubs: dict[ClubId, Club]
    staff: Mapping[ClubId, Sequence[StaffMember]]
    managers: Mapping[ClubId, Manager]
    entries: Mapping[ClubId, Sequence[SquadEntry]]
    mood: MoodConfig
    level: float = 0.0  # the league level players outside the league are scaled from
    unhappy: frozenset[str] = frozenset()
    listings: dict[str, TransferListing] = field(default_factory=dict)
    deals: Counter[ClubId] = field(default_factory=Counter)
    transfers: list[Transfer] = field(default_factory=list)
    bids: list[TransferBid] = field(default_factory=list)
    offers: list[ContractOffer] = field(default_factory=list)
    postings: list[Posting] = field(default_factory=list)
    events: list[WorldEvent] = field(default_factory=list)
    modifiers: list[StateModifier] = field(default_factory=list)
    touched: set[ClubId] = field(default_factory=set)
    sold: set[str] = field(default_factory=set)

    def league_ids(self) -> list[ClubId]:
        """The league's clubs, in id order (everyone but the outside world)."""
        return sorted(club_id for club_id in self.clubs if club_id != OUTSIDE_WORLD)

    def squad(self, club_id: ClubId) -> list[Player]:
        """Everyone under contract with the club, prospects included, in id order."""
        return sorted(
            (
                p
                for p in self.players.values()
                if p.contract and p.contract.club_id == club_id and p.status is PlayerStatus.ACTIVE
            ),
            key=lambda item: item.id,
        )

    def seniors(self, club_id: ClubId) -> list[Player]:
        """A club's senior players, in id order."""
        return sorted(
            (
                p
                for p in self.players.values()
                if p.contract
                and p.contract.club_id == club_id
                and not p.is_youth
                and p.status is PlayerStatus.ACTIVE
            ),
            key=lambda item: item.id,
        )

    def wage_bill(self, club_id: ClubId) -> Money:
        """The club's weekly wage bill for players under contract."""
        return sum(p.contract.wage_weekly for p in self.seniors(club_id) if p.contract)


def incoming_role(player: Player, squad: Sequence[Player]) -> SquadRole:
    """Key player if he would be among the squad's best seven, otherwise rotation."""
    ranked = sorted((p.ability_current for p in squad), reverse=True)
    cutoff = ranked[KEY_RANK - 1] if len(ranked) >= KEY_RANK else 0
    return SquadRole.KEY if player.ability_current >= cutoff else SquadRole.ROTATION


@dataclass(frozen=True, slots=True)
class Deal:
    """A deal both clubs and the player have agreed."""

    player: Player
    buyer: ClubId
    seller: ClubId | None  # None for a free agent
    fee: Money
    terms: Agreed
    bid_round: int


def complete(market: Market, deal: Deal) -> Transfer:
    """Carry out a deal: contract, squad, money, records and news change together."""
    player, buyer, seller = deal.player, deal.buyer, deal.seller
    squad = market.seniors(buyer)
    contract = (player.contract or _blank_contract(buyer, market.today)).model_copy(
        update={
            "club_id": buyer,
            "start": market.today,
            "end": contract_end(market.today, deal.terms.length_years),
            "wage_weekly": deal.terms.wage,
            "squad_role": incoming_role(player, squad),
        }
    )
    market.players[player.id] = player.model_copy(
        update={
            "contract": contract,
            "status": PlayerStatus.ACTIVE,
            "squad_status": SquadStatus.FIRST_TEAM,
            "is_youth": False,
            "squad_number": None,
        }
    )
    transfer = _record(market, deal)
    _move_money(market, deal, transfer)
    market.deals[buyer] += 1
    market.touched.update(c for c in (buyer, seller) if c is not None)
    market.sold.add(player.id)
    market.events.append(_news(market, deal, transfer))
    market.modifiers.append(_welcome(market, player))
    return transfer


def _blank_contract(club: ClubId, today: dt.date) -> Contract:
    """The starting point for a free agent's new contract (every field is then replaced)."""
    return Contract(club_id=club, start=today, end=today, wage_weekly=0)


def _record(market: Market, deal: Deal) -> Transfer:
    window, today = market.window, market.today
    seller = deal.seller or OUTSIDE_WORLD
    key = (window.id, deal.player.id, deal.buyer)
    transfer = Transfer(
        id=Id(derive_id("transfer", *key)),
        player_id=PlayerId(deal.player.id),
        from_club_id=seller,
        to_club_id=deal.buyer,
        fee=deal.fee,
        completed_on=today,
    )
    market.transfers.append(transfer)
    bid_id = Id(derive_id("bid", *key))
    market.bids.append(
        TransferBid(
            id=bid_id,
            window_id=window.id,
            player_id=PlayerId(deal.player.id),
            from_club_id=seller,
            to_club_id=deal.buyer,
            fee=deal.fee,
            round=deal.bid_round,
            status="accepted",
        )
    )
    market.offers.append(
        ContractOffer(
            id=Id(derive_id("offer", *key)),
            bid_id=bid_id,
            player_id=PlayerId(deal.player.id),
            club_id=deal.buyer,
            wage_weekly=deal.terms.wage,
            length_years=deal.terms.length_years,
            status="accepted",
            round=deal.terms.round,
        )
    )
    return transfer


def _move_money(market: Market, deal: Deal, transfer: Transfer) -> None:
    """The two ledger legs and the transfer budgets; a free agent moves no fee."""
    if deal.fee <= 0:
        return
    ref = {"transfer_id": transfer.id}
    market.postings.append(
        Posting(
            deal.buyer, market.today, LedgerCategory.TRANSFER_FEES, -deal.fee, "transfer_fee", ref
        )
    )
    buyer = market.clubs[deal.buyer]
    market.clubs[deal.buyer] = _budget(buyer, -deal.fee)
    if deal.seller is not None:
        market.postings.append(
            Posting(
                deal.seller, market.today, LedgerCategory.PLAYER_SALES, deal.fee, "player_sale", ref
            )
        )
        market.clubs[deal.seller] = _budget(market.clubs[deal.seller], deal.fee)


def _budget(club: Club, change: Money) -> Club:
    budget = max(0, club.finances.transfer_budget + change)
    return club.model_copy(
        update={"finances": club.finances.model_copy(update={"transfer_budget": budget})}
    )


def _news(market: Market, deal: Deal, transfer: Transfer) -> WorldEvent:
    participants = [
        EntityRef(kind=EntityKind.PLAYER, id=Id(deal.player.id)),
        EntityRef(kind=EntityKind.CLUB, id=Id(deal.buyer)),
    ]
    if deal.seller is not None:
        participants.append(EntityRef(kind=EntityKind.CLUB, id=Id(deal.seller)))
    return WorldEvent(
        id=Id(derive_id("world_event", transfer.id)),
        date=market.today,
        kind="transfer_completed",
        participants=tuple(participants),
        facts={"fee": deal.fee, "value": deal.player.market_value, "transfer_id": transfer.id},
        visibility=ModifierVisibility.PUBLIC,
        origin="rule",
    )


def _welcome(market: Market, player: Player) -> StateModifier:
    spec = ModifierSpec(
        StateKind.NEW_SIGNING_ENTHUSIASM,
        player.id,
        SIGNING_ENTHUSIASM,
        ModifierSource(origin="rule"),
    )
    return new_modifier(spec, market.today, market.mood)
