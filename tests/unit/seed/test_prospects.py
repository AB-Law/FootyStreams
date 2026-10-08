from __future__ import annotations

import datetime as dt

from footystreams.domain.prospects import ProspectRequest
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import ClubId, Position
from footystreams.seed.prospects import SeedProspectFactory
from tests.factories.world import make_generation_context, make_world

TODAY = dt.date(2032, 6, 1)
CONTEXT = make_generation_context(1)
FACTORY = SeedProspectFactory(CONTEXT.tables, CONTEXT.geography)
WORLD = make_world(1)


def _request(index: int, *, youth: bool = True, club: bool = True) -> ProspectRequest:
    return ProspectRequest(
        key=f"2032:clb_00001:{index}",
        position=Position.CM,
        age=17 if youth else 27,
        ability=40,
        potential_bonus=8,
        region=WORLD.clubs[0].location.region,
        club_reputation=60,
        club_id=ClubId("clb_00001") if club else None,
        youth=youth,
    )


def test_create__one_player_per_request_in_order_with_ids_from_the_keys() -> None:
    players = FACTORY.create([_request(0), _request(1)], WORLD.players, (TODAY, WorldRng(1)))
    assert len(players) == 2
    assert players[0].id != players[1].id
    assert players[0].id.startswith("plr_")
    again = FACTORY.create([_request(1)], WORLD.players, (TODAY, WorldRng(9)))
    assert again[0].id == players[1].id


def test_create__same_request_and_seed__same_player() -> None:
    first = FACTORY.create([_request(0)], WORLD.players, (TODAY, WorldRng(3)))
    assert first == FACTORY.create([_request(0)], WORLD.players, (TODAY, WorldRng(3)))


def test_create__youth_and_senior_requests__get_the_right_flags_and_ages() -> None:
    youth = FACTORY.create([_request(0)], WORLD.players, (TODAY, WorldRng(1)))[0]
    senior = FACTORY.create([_request(1, youth=False)], WORLD.players, (TODAY, WorldRng(1)))[0]
    agent = FACTORY.create(
        [_request(2, youth=False, club=False)], WORLD.players, (TODAY, WorldRng(1))
    )[0]
    assert youth.is_youth
    assert youth.age_on(TODAY) == 17
    assert not senior.is_youth
    assert senior.age_on(TODAY) == 27
    assert agent.status.value == "free_agent"


def test_create__names_stay_unique_against_the_people_already_in_the_world() -> None:
    requests = [_request(i, youth=False) for i in range(30)]
    players = FACTORY.create(requests, WORLD.players, (TODAY, WorldRng(2)))
    taken = {p.known_as for p in WORLD.players}
    new = [p.known_as for p in players]
    assert not taken & set(new)
    assert len(set(new)) == len(new)


def test_create__ability_lands_near_the_request() -> None:
    players = FACTORY.create(
        [_request(i, youth=False) for i in range(8)], WORLD.players, (TODAY, WorldRng(2))
    )
    assert all(abs(p.ability_current - 40) <= 8 for p in players)


def test_create__the_date_decides_the_birth_year() -> None:
    later_day = dt.date(2040, 6, 1)
    later = FACTORY.create([_request(0)], WORLD.players, (later_day, WorldRng(1)))[0]
    assert later.age_on(later_day) == 17
