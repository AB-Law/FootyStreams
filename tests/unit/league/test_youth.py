from __future__ import annotations

import datetime as dt

from footystreams.domain.contract import SquadRole
from footystreams.domain.player import SquadStatus
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import Position
from footystreams.league.youth import (
    contract_end,
    intake_requests,
    promoted,
    signed_prospect,
    youth_contract,
)
from tests.factories.league_config import make_development_config
from tests.factories.world import make_world

CONFIG = make_development_config().youth
WORLD = make_world(1)
CLUB = WORLD.clubs[2]
TODAY = dt.date(2032, 6, 1)
POSITIONS = [Position.GK, Position.CB, Position.CB, Position.CM, Position.ST]


def test_intake_requests__one_per_academy_place_with_ages_in_range() -> None:
    requests = intake_requests(CLUB, (POSITIONS, 60.0), "2032", CONFIG, WorldRng(1))
    assert len(requests) == CLUB.academy.intake_size
    assert {r.position for r in requests} <= set(POSITIONS)
    assert all(CONFIG.intake_age[0] <= r.age <= CONFIG.intake_age[1] for r in requests)
    assert len({r.key for r in requests}) == len(requests)
    assert all(r.club_id == CLUB.id for r in requests)
    assert all(r.youth for r in requests)


def test_intake_requests__better_academy_and_league__asks_for_better_players() -> None:
    rich = CLUB.model_copy(
        update={
            "academy": CLUB.academy.model_copy(update={"intake_quality": 1.0, "intake_size": 30})
        }
    )
    poor = CLUB.model_copy(
        update={
            "academy": CLUB.academy.model_copy(update={"intake_quality": 0.0, "intake_size": 30})
        }
    )
    good = intake_requests(rich, (POSITIONS, 60.0), "2032", CONFIG, WorldRng(1))
    bad = intake_requests(poor, (POSITIONS, 60.0), "2032", CONFIG, WorldRng(1))
    assert sum(r.ability for r in good) > sum(r.ability for r in bad)
    assert good[0].potential_bonus > bad[0].potential_bonus


def test_intake_requests__same_inputs__same_requests() -> None:
    one = intake_requests(CLUB, (POSITIONS, 60.0), "2032", CONFIG, WorldRng(5))
    assert one == intake_requests(CLUB, (POSITIONS, 60.0), "2032", CONFIG, WorldRng(5))


def test_contract_end__is_the_thirtieth_of_june_the_given_number_of_seasons_on() -> None:
    assert contract_end(dt.date(2032, 6, 1), 1) == dt.date(2032, 6, 30)
    assert contract_end(dt.date(2032, 6, 1), 3) == dt.date(2034, 6, 30)
    assert contract_end(dt.date(2032, 7, 1), 1) == dt.date(2033, 6, 30)


def test_youth_contract__is_a_prospect_deal_at_the_configured_wage() -> None:
    contract = youth_contract(CLUB.id, TODAY, CONFIG)
    assert contract.squad_role is SquadRole.PROSPECT
    assert contract.wage_weekly == CONFIG.wage_weekly
    assert contract.end == contract_end(TODAY, CONFIG.contract_years)


def test_signed_prospect__is_a_valued_youth_on_the_academy_contract() -> None:
    base = next(p for p in WORLD.players if p.is_youth).model_copy(update={"contract": None})
    signed = signed_prospect(base, CLUB.id, TODAY, CONFIG)
    assert signed.contract is not None
    assert signed.contract.club_id == CLUB.id
    assert signed.squad_status is SquadStatus.YOUTH
    assert signed.is_youth
    assert signed.market_value > 0


def test_promoted__becomes_a_valid_senior_with_a_rotation_deal() -> None:
    youth = next(p for p in WORLD.players if p.is_youth and p.contract is not None)
    senior = promoted(youth, TODAY)
    assert not senior.is_youth
    assert senior.squad_status is SquadStatus.FIRST_TEAM
    assert senior.contract is not None
    assert senior.contract.squad_role is SquadRole.ROTATION
    assert senior.contract.wage_weekly >= youth.contract.wage_weekly  # type: ignore[union-attr]
    assert max(senior.position_competence.values()) >= 85
