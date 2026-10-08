from __future__ import annotations

import datetime as dt
import statistics

from footystreams.domain.contract import SquadRole
from footystreams.domain.injury import Injury, InjurySeverity
from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.league.needs import GROUPS, Need
from footystreams.league.scouting import Perception
from footystreams.league.transfer_rules import (
    FeeTalks,
    can_afford,
    desire,
    medical_passes,
    negotiate_fee,
    opening_bid,
    reservation_price,
)
from tests.factories.league_config import make_transfer_config
from tests.factories.world import make_world

CONFIG = make_transfer_config()
VALUATION, NEEDS, MEDICAL = CONFIG.valuation, CONFIG.needs, CONFIG.medical
WORLD = make_world(1)
PLAYER = WORLD.players[3]
NEED = Need("MID", 0.5, 60, GROUPS["MID"])
VALUE = 10_000_000


def _talks(desire_: float = 0.5, urgency: float = 0.0, reservation: int = VALUE) -> FeeTalks:
    return FeeTalks(VALUE, desire_, urgency, reservation)


def test_desire__grows_with_perceived_quality_and_is_a_unit() -> None:
    low = desire(Perception(55, 60, 1.0), NEED, 27, VALUATION)
    high = desire(Perception(75, 80, 1.0), NEED, 27, VALUATION)
    assert 0.0 <= low < high <= 1.0


def test_desire__young_players_are_also_wanted_for_their_potential() -> None:
    perception = Perception(60, 85, 1.0)
    assert desire(perception, NEED, 19, VALUATION) > desire(perception, NEED, 29, VALUATION)


def test_opening_bid__wanting_and_needing_more_means_bidding_more() -> None:
    cheap = statistics.mean(
        opening_bid(_talks(0.1, 0.0), VALUATION, WorldRng(s)) for s in range(60)
    )
    keen = statistics.mean(opening_bid(_talks(0.9, 1.0), VALUATION, WorldRng(s)) for s in range(60))
    assert keen > cheap
    assert abs(cheap - VALUE * (1 + VALUATION.desire_weight * 0.1)) < VALUE * 0.05


def test_reservation_price__key_players_cost_more_backups_less_and_trouble_discounts() -> None:
    def price(role: SquadRole, ask: int | None = None, *, distressed: bool = False) -> int:
        return reservation_price(VALUE, role, ask, (VALUATION, distressed))

    assert price(SquadRole.KEY) > price(SquadRole.ROTATION) > price(SquadRole.BACKUP)
    assert price(SquadRole.ROTATION, distressed=True) < price(SquadRole.ROTATION)
    assert price(SquadRole.BACKUP, ask=VALUE * 2) == VALUE * 2


def test_negotiate_fee__a_generous_buyer_closes_in_round_one() -> None:
    deal = negotiate_fee(_talks(1.0, 1.0, reservation=int(VALUE * 0.5)), VALUATION, WorldRng(1))
    assert deal is not None
    assert deal.round == 1


def test_negotiate_fee__bids_rise_each_round_and_never_pass_the_ceiling() -> None:
    results = [
        negotiate_fee(_talks(0.5, 0.0, reservation=int(VALUE * 1.2)), VALUATION, WorldRng(s))
        for s in range(200)
    ]
    done = [r for r in results if r is not None]
    assert done
    assert {r.round for r in done} <= {1, 2, 3}
    assert any(r.round > 1 for r in done)
    assert max(r.fee for r in done) <= VALUE * (1 + 0.25 + 0.25 + 3 * 0.05) * (
        1 + VALUATION.ceiling_margin
    )


def test_negotiate_fee__a_seller_who_wants_far_more_refuses() -> None:
    assert negotiate_fee(_talks(0.2, 0.0, reservation=VALUE * 3), VALUATION, WorldRng(1)) is None


def test_negotiate_fee__same_stream__same_outcome() -> None:
    talks = _talks(0.5, 0.2, reservation=int(VALUE * 1.1))
    assert negotiate_fee(talks, VALUATION, WorldRng(8)) == negotiate_fee(
        talks, VALUATION, WorldRng(8)
    )


def test_medical_passes__injured_and_injury_prone_players_fail_more() -> None:
    def passes(player: Player, n: int = 600) -> float:
        return sum(medical_passes(player, MEDICAL, WorldRng(s)) for s in range(n)) / n

    fit = PLAYER.model_copy(
        update={
            "current_injury": None,
            "hidden": PLAYER.hidden.model_copy(update={"injury_proneness": 5}),
        }
    )
    prone = fit.model_copy(
        update={"hidden": fit.hidden.model_copy(update={"injury_proneness": 99})}
    )
    injury = Injury(
        type="x",
        body_part="knee",
        severity=InjurySeverity.MODERATE,
        started_on=dt.date(2032, 1, 1),
        expected_return_on=dt.date(2032, 3, 1),
    )
    hurt = fit.model_copy(update={"current_injury": injury})
    assert passes(fit) > passes(prone) > passes(hurt)
    assert passes(fit) > 0.9


def test_can_afford__budget_overdraft_and_wage_limits_all_apply() -> None:
    club = WORLD.clubs[6]
    rich = club.model_copy(
        update={
            "finances": club.finances.model_copy(
                update={
                    "transfer_budget": 20_000_000,
                    "balance": 20_000_000,
                    "credit_limit": 0,
                    "wage_budget_weekly": 100_000,
                }
            )
        }
    )
    assert can_afford(rich, (5_000_000, 10_000, 50_000), NEEDS, urgent=False)
    assert not can_afford(
        rich, (15_000_000, 10_000, 50_000), NEEDS, urgent=False
    )  # over half the budget
    assert can_afford(rich, (15_000_000, 10_000, 50_000), NEEDS, urgent=True)
    assert not can_afford(rich, (25_000_000, 10_000, 50_000), NEEDS, urgent=True)  # over the budget
    assert not can_afford(
        rich, (5_000_000, 10_000, 120_000), NEEDS, urgent=False
    )  # wage bill too high
    broke = rich.model_copy(
        update={"finances": rich.finances.model_copy(update={"balance": 1_000_000})}
    )
    assert not can_afford(
        broke, (5_000_000, 10_000, 50_000), NEEDS, urgent=False
    )  # past the overdraft
