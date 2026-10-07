"""The outside world: a synthetic club standing for every club outside the league.

It supplies players to buy and pays fees for the league's best. It is a real (reserved) club row
so fees are ordinary ledger legs and the books still close: every fee a league club pays or
receives has a mirror leg on the other side, the outside world included.
"""

from __future__ import annotations

from footystreams.domain.club import Club
from footystreams.domain.player import PlayerStatus
from footystreams.domain.prospects import ProspectFactory, ProspectRequest
from footystreams.domain.rng import WorldRng
from footystreams.domain.transfer import OUTSIDE_WORLD
from footystreams.domain.types import Position
from footystreams.league.retirement import retired, retirement_news
from footystreams.league.squad import signed_free_agent
from footystreams.league.tables import LeagueTables
from footystreams.league.transfer_market import Market

OUTSIDE_NAME = "The Wider World"
OUTSIDE_CODE = "OUT"
SUPPLY_POSITIONS = (
    Position.GK, Position.CB, Position.CB, Position.RB, Position.LB, Position.DM, Position.CM,
    Position.CM, Position.AM, Position.RW, Position.LW, Position.ST, Position.ST,
)  # fmt: skip
POOL_CAP_FACTOR = 2  # the outside pool may hold this many times the supply size


def outside_club(template: Club) -> Club:
    """The reserved club row, built from a league club so it is a valid ``Club``."""
    finances = template.finances.model_copy(
        update={
            "balance": 0,
            "wage_budget_weekly": 0,
            "transfer_budget": 0,
            "debt": 0,
            "credit_limit": 0,
            "sponsor_deals": (),
            "broadcast_share": 0,
        }
    )
    return template.model_copy(
        update={
            "id": OUTSIDE_WORLD,
            "name": OUTSIDE_NAME,
            "short_name": OUTSIDE_NAME,
            "short_code": OUTSIDE_CODE,
            "nickname": "",
            "finances": finances,
            "rivalries": (),
            "manager_id": None,
            "staff_ids": (),
            "academy": template.academy.model_copy(update={"intake_size": 0, "prospect_ids": ()}),
        }
    )


def ensure_outside(market: Market) -> None:
    """Add the outside club to the market if the database does not have it yet."""
    if OUTSIDE_WORLD not in market.clubs:
        template = market.clubs[market.league_ids()[0]]
        market.clubs[OUTSIDE_WORLD] = outside_club(template)


def outside_players(market: Market) -> list[str]:
    """Ids of the players the outside world currently holds."""
    return sorted(
        p.id
        for p in market.players.values()
        if p.contract and p.contract.club_id == OUTSIDE_WORLD and p.status is PlayerStatus.ACTIVE
    )


def top_up_supply(
    market: Market, tables: LeagueTables, prospects: ProspectFactory, rng: WorldRng
) -> None:
    """Create outside players until the supply has its configured size."""
    config = tables.transfer.outside
    missing = max(0, config.supply_size - len(outside_players(market)))
    region = market.clubs[market.league_ids()[0]].location.region
    low, high = config.supply_ability
    requests: list[ProspectRequest] = []
    for index in range(missing):
        stream = rng.fork(f"request:{index}")
        requests.append(
            ProspectRequest(
                key=f"outside:{market.window.id}:{market.today.isoformat()}:{index}",
                position=SUPPLY_POSITIONS[index % len(SUPPLY_POSITIONS)],
                age=stream.randint(*config.supply_age),
                ability=round(market.level * stream.uniform(low, high)),
                potential_bonus=0,
                region=region,
                club_reputation=market.clubs[OUTSIDE_WORLD].club_reputation,
                club_id=None,
                youth=False,
            )
        )
    known = list(market.players.values())
    for player in prospects.create(requests, known, (market.today, rng.fork("create"))):
        market.players[player.id] = signed_free_agent(player, OUTSIDE_WORLD, market.today, 1)


def trim_supply(market: Market, tables: LeagueTables) -> None:
    """At the close of a window the weakest outside players beyond the cap leave the game."""
    cap = tables.transfer.outside.supply_size * POOL_CAP_FACTOR
    held = sorted(
        (market.players[pid] for pid in outside_players(market)),
        key=lambda p: (-p.ability_current, p.id),
    )
    for player in held[cap:]:
        market.players[player.id] = retired(player, market.today)
        market.events.append(retirement_news(player, market.today, "left_the_game"))
