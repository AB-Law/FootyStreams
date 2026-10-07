from __future__ import annotations

import datetime as dt
from collections import Counter

import pytest

from footystreams.domain.contract import SquadRole
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import ClubId, Position
from footystreams.seed.geography import generate_geography
from footystreams.seed.ids import IdMint, base36
from footystreams.seed.names.book import NameBook
from footystreams.seed.players.condition import starting_condition
from footystreams.seed.players.contract import contract_for, wage_from_value
from footystreams.seed.players.generator import PlayerSpec, generate_player, prior_stints
from footystreams.seed.players.mind import generate_hidden, generate_personality
from footystreams.seed.players.positions import resolve_role
from footystreams.seed.static.tables import load_static_tables
from tests.factories.world import WORLD_START, make_generation_context

SAMPLES = 400


def test_base36__known_values() -> None:
    assert base36(0) == "00000"
    assert base36(35, width=1) == "z"
    assert base36(36, width=2) == "10"


def test_base36__negative__raises() -> None:
    with pytest.raises(ValueError, match="negative"):
        base36(-1)


def test_id_mint__counts_per_kind_and_rejects_unknown_kind() -> None:
    mint = IdMint()
    assert mint.next("player") == "plr_00001"
    assert mint.next("player") == "plr_00002"
    assert mint.next("club") == "clb_00001"
    assert mint.minted("player") == 2
    with pytest.raises(ValueError, match="unknown id kind"):
        mint.next("spaceship")


def test_geography__home_nation_has_six_regions_and_foreign_nations_have_cities() -> None:
    geography = generate_geography(WorldRng(1), NameBook.from_static(), IdMint())
    assert len(geography.regions()) == 6
    assert len(geography.foreign) == 8
    assert all(geography.cities[nation.id] for nation in geography.nations)
    names = [city.name for cities in geography.cities.values() for city in cities]
    assert len(names) == len(set(names))


def test_geography__pick_city_prefers_the_requested_region() -> None:
    geography = generate_geography(WorldRng(1), NameBook.from_static(), IdMint())
    picks = {geography.pick_city(WorldRng(i), geography.home.id, "isles").region for i in range(10)}
    assert picks == {"isles"}


def test_personality__dispositions_are_valid_and_labelled() -> None:
    rng = WorldRng(3)
    people = [generate_personality(rng.fork(str(i)), 25, youth=False) for i in range(SAMPLES)]
    styles = Counter(p.interview_style for p in people)
    assert len(styles) >= 5
    assert any(p.archetype_tags for p in people)


def test_personality__veterans_more_professional_than_youth_on_average() -> None:
    rng = WorldRng(3)
    veterans = [
        generate_personality(rng.fork(f"v{i}"), 33, youth=False).professionalism
        for i in range(SAMPLES)
    ]
    youth = [
        generate_personality(rng.fork(f"y{i}"), 17, youth=True).professionalism
        for i in range(SAMPLES)
    ]
    assert sum(veterans) / SAMPLES > sum(youth) / SAMPLES + 8


def test_hidden__extreme_characters_exist_in_a_large_sample() -> None:
    rng = WorldRng(11)
    personality = generate_personality(rng, 25, youth=False)
    hidden = [generate_hidden(rng.fork(str(i)), personality) for i in range(2000)]
    assert any(h.injury_proneness <= 10 for h in hidden)
    assert any(h.dirtiness >= 75 for h in hidden)
    assert any(h.consistency <= 35 for h in hidden)


def test_resolve_role__unknown_role__raises() -> None:
    catalog = load_static_tables().roles
    with pytest.raises(ValueError, match="no role id"):
        resolve_role(catalog, "telepathic_forward", Position.ST)


def test_resolve_role__expands_multi_position_roles() -> None:
    catalog = load_static_tables().roles
    assert resolve_role(catalog, "full_back", Position.LB) == "full_back_lb"
    assert resolve_role(catalog, "poacher", Position.ST) == "poacher"


def test_starting_condition__mostly_fit_with_a_few_injuries() -> None:
    catalog = load_static_tables().injuries
    rng = WorldRng(2)
    conditions = [starting_condition(rng.fork(str(i)), catalog, WORLD_START) for i in range(2000)]
    injured = [c for c in conditions if c.injury is not None]
    assert 0.01 < len(injured) / 2000 < 0.06
    assert all(
        c.injury.expected_return_on >= WORLD_START - dt.timedelta(days=30)
        for c in injured
        if c.injury
    )
    assert all(0.8 <= c.fitness <= 0.97 for c in conditions)


def test_wage_from_value__is_sublinear_and_monotone() -> None:
    low, high = wage_from_value(1_000_000), wage_from_value(16_000_000)
    assert 0 < low < high < 16 * low


def test_contract_for__staggers_remaining_terms_and_ends_on_june_30() -> None:
    ctx = make_generation_context()
    rng = WorldRng(5)
    spec = PlayerSpec(Position.CM, 26, 60, ClubId("clb_00001"), "highland", 50)
    players = [generate_player(spec, ctx, rng.fork(str(i))) for i in range(60)]
    contracts = [
        contract_for(rng.fork(f"c{i}"), p, ClubId("clb_00001"), SquadRole.ROTATION, WORLD_START)
        for i, p in enumerate(players)
    ]
    assert all((c.end.month, c.end.day) == (6, 30) for c in contracts)
    assert all(c.start <= WORLD_START < c.end for c in contracts)
    assert len({c.end.year for c in contracts}) >= 4


def test_prior_stints__children_have_none_and_adults_are_ordered() -> None:
    rng = WorldRng(1)
    child = PlayerSpec(Position.CM, 17, 40, ClubId("clb_00001"), "highland", 50, youth=True)
    assert prior_stints(rng, child, WORLD_START) == ()
    adult = PlayerSpec(Position.ST, 30, 60, ClubId("clb_00001"), "highland", 50)
    stints = prior_stints(WorldRng(4), adult, WORLD_START)
    assert list(stints) == sorted(stints, key=lambda s: s.from_date)
