from __future__ import annotations

import datetime as dt

from footystreams.domain.player import CareerStint, Player, PlayerStatus, SquadStatus
from footystreams.domain.rng import WorldRng
from footystreams.league.retirement import (
    choose_retirements,
    retired,
    retirement_chance,
    retirement_news,
)
from tests.factories.league_config import make_development_config
from tests.factories.world import make_world

CONFIG = make_development_config().retirement
TODAY = dt.date(2032, 6, 1)
PLAYERS = list(make_world(1).players)


def aged(player: Player, age: int) -> Player:
    born = TODAY.replace(year=TODAY.year - age) - dt.timedelta(days=100)
    return player.model_copy(update={"date_of_birth": born})


def test_retirement_chance__young_players_never_retire() -> None:
    assert retirement_chance(aged(PLAYERS[0], 28), 60, TODAY, CONFIG) == 0.0


def test_retirement_chance__rises_with_age() -> None:
    chances = [retirement_chance(aged(PLAYERS[0], a), 60, TODAY, CONFIG) for a in (32, 35, 37, 40)]
    assert chances == sorted(chances)
    assert chances[-1] > chances[0] > 0


def test_retirement_chance__weaker_players_retire_sooner() -> None:
    weak = aged(PLAYERS[0], 35).model_copy(update={"ability_current": 30, "ability_potential": 40})
    strong = aged(PLAYERS[0], 35).model_copy(
        update={"ability_current": 85, "ability_potential": 90}
    )
    assert retirement_chance(weak, 60, TODAY, CONFIG) > retirement_chance(strong, 60, TODAY, CONFIG)


def test_retirement_chance__is_a_probability() -> None:
    old = aged(PLAYERS[0], 45).model_copy(update={"ability_current": 5, "ability_potential": 10})
    assert 0.0 <= retirement_chance(old, 90, TODAY, CONFIG) <= 1.0


def test_choose_retirements__same_seed_same_people_and_only_the_old() -> None:
    squad = [aged(p, 20 + (i % 20)) for i, p in enumerate(PLAYERS[:120])]
    first = choose_retirements(squad, TODAY, CONFIG, WorldRng(4))
    assert [p.id for p in first] == [
        p.id for p in choose_retirements(squad, TODAY, CONFIG, WorldRng(4))
    ]
    assert first
    assert all(p.age_on(TODAY) >= 32 for p in first)


def test_choose_retirements__nobody_to_consider__returns_nothing() -> None:
    gone = PLAYERS[0].model_copy(update={"status": PlayerStatus.RETIRED})
    assert choose_retirements([gone], TODAY, CONFIG, WorldRng(1)) == []
    assert choose_retirements([], TODAY, CONFIG, WorldRng(1)) == []


def test_retired__clears_contract_and_closes_the_open_spell() -> None:
    player = PLAYERS[0]
    open_spell = CareerStint(club_id=player.contract.club_id, from_date=dt.date(2030, 7, 1))  # type: ignore[union-attr]
    done = retired(player.model_copy(update={"career_history": (open_spell,)}), TODAY)
    assert done.status is PlayerStatus.RETIRED
    assert done.squad_status is SquadStatus.FREE_AGENT
    assert done.contract is None
    assert done.career_history[-1].to_date == TODAY


def test_retirement_news__is_a_public_event_about_the_player() -> None:
    event = retirement_news(PLAYERS[0], TODAY)
    assert event.kind == "retirement"
    assert event.participants[0].id == PLAYERS[0].id
