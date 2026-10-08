from __future__ import annotations

import datetime as dt

from footystreams.domain.contract import SquadRole
from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.league.contracts import (
    Proposal,
    club_wants,
    expire_contracts,
    loyalty_bonus,
    market_wage,
    negotiate,
    willingness,
)
from tests.factories.league_config import make_transfer_config
from tests.factories.world import make_world

CONFIG = make_transfer_config()
TERMS, RENEWAL = CONFIG.terms, CONFIG.renewal
WORLD = make_world(1)
_BASE = WORLD.players[10]
PLAYER = _BASE.model_copy(  # neutral mood and ambition: nothing pulls either way
    update={"morale": 0.5, "personality": _BASE.personality.model_copy(update={"ambition": 50})}
)
TODAY = dt.date(2032, 6, 1)
WAGE = market_wage(PLAYER, TODAY)


def _score(wage_multiple: float, reputation: int = 60, **personality: int) -> float:
    player = PLAYER.model_copy(
        update={"personality": PLAYER.personality.model_copy(update=personality), "reputation": 60}
    )
    proposal = Proposal(reputation, round(WAGE * wage_multiple), current_club=False)
    return willingness(player, proposal, WAGE, TERMS)


def test_willingness__a_better_wage_is_always_more_attractive() -> None:
    assert _score(1.2) > _score(1.0) > _score(0.8)


def test_willingness__ambitious_players_care_about_the_clubs_standing() -> None:
    assert _score(1.0, reputation=90, ambition=95) > _score(1.0, reputation=30, ambition=95)
    assert _score(1.0, reputation=90, ambition=5) < _score(1.0, reputation=30, ambition=5)


def test_willingness__a_free_agent_is_easier_to_sign() -> None:
    base = Proposal(60, WAGE, current_club=False)
    free = Proposal(60, WAGE, current_club=False, free_agent=True)
    assert willingness(PLAYER, free, WAGE, TERMS) > willingness(PLAYER, base, WAGE, TERMS)


def test_loyalty_bonus__only_for_the_current_club_and_only_for_loyal_players() -> None:
    loyal = PLAYER.model_copy(
        update={"personality": PLAYER.personality.model_copy(update={"loyalty": 100})}
    )
    disloyal = PLAYER.model_copy(
        update={"personality": PLAYER.personality.model_copy(update={"loyalty": 0})}
    )
    here = Proposal(60, WAGE, current_club=True)
    away = Proposal(60, WAGE, current_club=False)
    assert loyalty_bonus(loyal, here, 0.2) > 0
    assert loyalty_bonus(loyal, away, 0.2) == 0
    assert loyalty_bonus(disloyal, here, 0.2) == 0


def test_negotiate__a_fair_offer_is_accepted_in_the_first_round_and_may_use_the_market_wage() -> (
    None
):
    agreed = negotiate(
        PLAYER, (PLAYER.reputation + 20, 1.0), (TERMS, RENEWAL), (TODAY, WorldRng(1), False)
    )
    assert agreed is not None
    assert agreed.round == 1
    assert agreed.wage == WAGE
    assert TERMS.length_years[0] <= agreed.length_years <= TERMS.length_years[1]


def test_negotiate__a_club_that_cannot_pay__fails_after_every_round() -> None:
    assert (
        negotiate(
            PLAYER, (PLAYER.reputation - 40, 0.2), (TERMS, RENEWAL), (TODAY, WorldRng(1), False)
        )
        is None
    )


def test_negotiate__a_stingy_first_offer_is_raised_in_later_rounds() -> None:
    stingy = negotiate(
        PLAYER, (PLAYER.reputation, 0.93), (TERMS, RENEWAL), (TODAY, WorldRng(1), False)
    )
    assert stingy is not None
    assert stingy.round > 1
    assert stingy.wage > round(WAGE * 0.93)


def test_negotiate__same_stream__same_terms() -> None:
    args = (PLAYER, (PLAYER.reputation, 0.95), (TERMS, RENEWAL), (TODAY, WorldRng(4), False))
    assert negotiate(*args) == negotiate(*args)


def test_club_wants__keeps_the_useful_and_lets_the_much_weaker_go() -> None:
    peers = [p for p in WORLD.players if p.contract and p.contract.club_id == WORLD.clubs[0].id]
    keeper = max(peers, key=lambda p: p.ability_current)
    weak = keeper.model_copy(update={"ability_current": 10, "ability_potential": 20})
    assert club_wants(keeper, peers, SquadRole.ROTATION, (RENEWAL, TODAY))
    assert not club_wants(weak, peers, SquadRole.BACKUP, (RENEWAL, TODAY))
    assert club_wants(weak, peers, SquadRole.KEY, (RENEWAL, TODAY))


def test_club_wants__nobody_over_the_age_limit() -> None:
    peers = [p for p in WORLD.players if p.contract and p.contract.club_id == WORLD.clubs[0].id]
    old = peers[0].model_copy(update={"date_of_birth": dt.date(1980, 1, 1)})
    assert not club_wants(old, peers, SquadRole.KEY, (RENEWAL, TODAY))


def _ending(player: Player, end: dt.date) -> Player:
    assert player.contract is not None
    return player.model_copy(update={"contract": player.contract.model_copy(update={"end": end})})


def test_expire_contracts__only_contracts_that_ended_before_today_release_their_player() -> None:
    club_players = [p for p in WORLD.players if p.contract][:6]
    ended = [_ending(p, dt.date(2032, 6, 30)) for p in club_players[:3]]
    live = [_ending(p, dt.date(2032, 7, 1)) for p in club_players[3:]]
    expiry = expire_contracts([*ended, *live], dt.date(2032, 7, 1))
    assert [p.id for p in expiry.players] == sorted(p.id for p in ended)
    assert all(p.contract is None for p in expiry.players)
    assert {e.kind for e in expiry.events} == {"contract_expired"}
    assert all(table == "squad_entries" for table, _ in expiry.deletions)
    assert len(expiry.deletions) == 3
