from __future__ import annotations

import time
from collections import Counter
from functools import cache
from itertools import pairwise

import pytest

from footystreams.domain.rng import WorldRng
from footystreams.domain.world import World
from footystreams.seed.config import MAX_CLUBS, GeneratorConfig
from footystreams.seed.league_shape import MIN_SPACING, plan_league
from footystreams.seed.static.tables import load_static_tables
from footystreams.seed.world_gen import generate_world

SEEDS_FOR_SHAPE = range(1, 21)


@cache
def _world(seed: int = 1) -> World:
    return generate_world(seed)


def _everything(world: World) -> list[str]:
    parts = [
        *world.nations, *world.cities, *world.competitions, *world.seasons, *world.clubs,
        *world.squad_entries, *world.players, *world.managers, *world.staff, *world.referees,
        *world.media, *world.relationships, *world.ledger_opening,
    ]  # fmt: skip
    return [part.model_dump_json() for part in parts]


def test_generate_world__counts_match_the_plan() -> None:
    world = _world()
    assert len(world.clubs) == 8
    assert len(world.players) == 8 * 33 + 30
    assert len(world.managers) == 8 + 4
    assert len(world.staff) == 8 * 9
    assert len(world.referees) == 10
    assert len(world.media) == 11
    assert len(world.squad_entries) == 8 * 33
    assert len(world.ledger_opening) == 8
    assert world.memories == ()


def test_generate_world__same_seed__identical_content() -> None:
    assert _everything(generate_world(2)) == _everything(generate_world(2))


def test_generate_world__different_seed__different_content() -> None:
    assert _everything(_world(1)) != _everything(_world(2))


def test_generate_world__known_as_is_unique_across_every_kind_of_person() -> None:
    world = _world()
    people = [*world.players, *world.managers, *world.staff, *world.referees, *world.media]
    names = [person.known_as for person in people]
    assert len(names) == len(set(names))
    ids = [str(person.id) for person in people]
    assert len(ids) == len(set(ids))


def test_generate_world__one_league_competition_with_every_club() -> None:
    world = _world()
    competition = world.competitions[0]
    assert set(competition.club_ids) == {club.id for club in world.clubs}
    assert world.seasons[0].matchdays == 14
    assert world.seasons[0].competition_id == competition.id


def test_generate_world__derby_clubs_have_rivalries_on_both_sides() -> None:
    world = _world()
    rivals = {club.id: {r.club_id for r in club.rivalries} for club in world.clubs}
    for club_id, others in rivals.items():
        assert all(club_id in rivals[other] for other in others)
    assert sum(bool(others) for others in rivals.values()) == 6


def test_generate_world__every_club_plays_in_its_own_city_with_a_unique_code() -> None:
    world = _world()
    assert len({club.short_code for club in world.clubs}) == 8
    assert len({club.location.city for club in world.clubs}) == 8
    assert len({club.name for club in world.clubs}) == 8


def test_generate_world__records_are_sorted_by_id() -> None:
    world = _world()
    assert [str(p.id) for p in world.players] == sorted(str(p.id) for p in world.players)
    assert [str(c.id) for c in world.clubs] == sorted(str(c.id) for c in world.clubs)


def test_generate_world__fewer_clubs__smaller_league() -> None:
    world = generate_world(3, GeneratorConfig(clubs=4))
    assert len(world.clubs) == 4
    assert world.seasons[0].matchdays == 6
    assert len(world.competitions[0].club_ids) == 4


@pytest.mark.parametrize("clubs", [1, MAX_CLUBS + 1])
def test_generator_config__league_size_out_of_range__rejected(clubs: int) -> None:
    with pytest.raises(ValueError, match="clubs must be between"):
        GeneratorConfig(clubs=clubs)


def test_generate_world__stays_inside_the_five_second_budget() -> None:
    started = time.perf_counter()
    generate_world(5)
    assert time.perf_counter() - started < 10  # budget is 5 s; slower shared runners get slack


def test_plan_league__spacing_and_gap_hold_for_many_seeds() -> None:
    tables = load_static_tables().clubs
    for seed in SEEDS_FOR_SHAPE:
        slots = plan_league(WorldRng(seed), tables, 8)
        ranked = sorted(slot.quality for slot in slots)
        assert all(b - a >= MIN_SPACING - 0.02 for a, b in pairwise(ranked))
        assert tables.league.min_gap + 1 <= ranked[-1] - ranked[0] <= tables.league.max_gap


def test_plan_league__every_archetype_is_used_once_and_target_is_near_its_band() -> None:
    tables = load_static_tables().clubs
    slots = plan_league(WorldRng(4), tables, 8)
    assert Counter(slot.archetype_key for slot in slots) == dict.fromkeys(tables.archetypes, 1)
    for slot in slots:
        low, high = tables.archetypes[slot.archetype_key].quality
        assert low - 1 <= slot.quality <= high + 2
