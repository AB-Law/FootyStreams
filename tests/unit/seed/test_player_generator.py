from __future__ import annotations

import statistics
import time

import pytest

from footystreams.domain.attributes import attribute_map
from footystreams.domain.player import Player
from footystreams.domain.ratings import compute_current_ability
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import ClubId, Position, RoleId
from footystreams.seed.players.context import GenerationContext
from footystreams.seed.players.generator import PlayerSpec, generate_player
from tests.factories.world import make_generation_context

CLUB = ClubId("clb_00001")
TOLERANCE = 1


def _spec(
    position: Position, target: int = 70, *, age: int = 26, youth: bool = False
) -> PlayerSpec:
    return PlayerSpec(
        position=position,
        age=age,
        target_ability=target,
        club_id=CLUB,
        region="highland",
        club_reputation=60,
        youth=youth,
    )


@pytest.fixture(scope="module")
def shared_context() -> GenerationContext:
    """Names and ids are stateful, so only tests that do not compare runs share this."""
    return make_generation_context()


def _generate(
    position: Position,
    seed: int = 1,
    *,
    target: int = 70,
    ctx: GenerationContext | None = None,
) -> Player:
    context = ctx or make_generation_context()
    return generate_player(_spec(position, target), context, WorldRng(seed))


@pytest.mark.parametrize("position", list(Position))
@pytest.mark.parametrize("target", [45, 62, 78, 88])
def test_generate_player__ability_matches_target(
    position: Position, target: int, shared_context: GenerationContext
) -> None:
    player = _generate(position, target=target, ctx=shared_context)
    catalog = shared_context.tables.roles
    assert abs(compute_current_ability(player, catalog) - target) <= TOLERANCE
    assert player.ability_current == compute_current_ability(player, catalog)


def test_generate_player__same_seed__identical_player() -> None:
    first = _generate(Position.ST, seed=5)
    second = _generate(Position.ST, seed=5)
    assert first.model_dump_json() == second.model_dump_json()


def test_generate_player__different_seed__different_player() -> None:
    assert _generate(Position.ST, seed=5) != _generate(Position.ST, seed=6)


def test_generate_player__potential_never_below_current() -> None:
    ctx = make_generation_context()
    rng = WorldRng(3)
    players = [
        generate_player(_spec(Position.CM, 60, age=18 + i % 14), ctx, rng.fork(str(i)))
        for i in range(40)
    ]
    assert all(p.ability_potential >= p.ability_current for p in players)


def test_generate_player__young_players_have_more_headroom_than_veterans() -> None:
    ctx = make_generation_context()
    rng = WorldRng(4)
    young = [
        generate_player(_spec(Position.CM, 55, age=18), ctx, rng.fork(f"y{i}")) for i in range(30)
    ]
    old = [
        generate_player(_spec(Position.CM, 55, age=33), ctx, rng.fork(f"o{i}")) for i in range(30)
    ]
    young_gap = statistics.mean(p.ability_potential - p.ability_current for p in young)
    old_gap = statistics.mean(p.ability_potential - p.ability_current for p in old)
    assert young_gap > old_gap + 5


def test_generate_player__profiles_are_spiky() -> None:
    ctx = make_generation_context()
    rng = WorldRng(7)
    positions = [Position.CB, Position.CM, Position.ST, Position.RW, Position.DM]
    spreads = []
    for index in range(50):
        player = generate_player(_spec(positions[index % 5], 65), ctx, rng.fork(str(index)))
        outfield = {
            **attribute_map(player.technical),
            **attribute_map(player.mental),
            **attribute_map(player.physical),
        }
        spreads.append(statistics.pstdev(outfield.values()))
    assert statistics.mean(spreads) >= 10


def test_generate_player__poachers_are_better_finishers_than_their_average() -> None:
    ctx = make_generation_context()
    rng = WorldRng(8)
    margins = []
    for index in range(80):
        player = generate_player(_spec(Position.ST, 70), ctx, rng.fork(str(index)))
        if any(r.role_id == RoleId("poacher") for r in player.preferred_roles):
            outfield = [
                *attribute_map(player.technical).values(),
                *attribute_map(player.mental).values(),
            ]
            margins.append(player.technical.finishing - statistics.mean(outfield))
    assert len(margins) >= 10
    assert statistics.mean(margins) > 5


def test_generate_player__goalkeepers_are_natural_keepers() -> None:
    player = _generate(Position.GK, target=70)
    assert player.primary_position is Position.GK
    assert player.position_competence[Position.GK] >= 92
    assert player.goalkeeping.shot_stopping > 55
    assert player.technical.finishing < 40


def test_generate_player__outfielders_have_low_goalkeeping() -> None:
    player = _generate(Position.CB, target=70)
    assert max(attribute_map(player.goalkeeping).values()) <= 20
    assert player.position_competence[Position.GK] <= 12


def test_generate_player__outfielders_competent_at_adjacent_positions() -> None:
    player = _generate(Position.RB, target=70)
    assert player.position_competence.get(Position.RWB, 0) >= 70


def test_generate_player__youth_flag_and_age() -> None:
    ctx = make_generation_context()
    player = generate_player(_spec(Position.CM, 42, age=17, youth=True), ctx, WorldRng(1))
    assert player.is_youth
    assert player.age_on(ctx.today) == 17


def test_generate_player__age_matches_request() -> None:
    ctx = make_generation_context()
    player = generate_player(_spec(Position.CM, age=29), ctx, WorldRng(2))
    assert player.age_on(ctx.today) == 29


def test_generate_player__market_value_is_positive_and_rises_with_ability() -> None:
    low = _generate(Position.CM, target=50)
    high = _generate(Position.CM, target=80)
    assert 0 < low.market_value < high.market_value


def test_generate_player__free_agent_has_no_club_status() -> None:
    ctx = make_generation_context()
    spec = PlayerSpec(Position.CM, 27, 50, None, "highland", 40)
    player = generate_player(spec, ctx, WorldRng(2))
    assert player.status.value == "free_agent"
    assert player.squad_status.value == "free_agent"


def test_generate_player__speed_budget() -> None:
    ctx = make_generation_context()
    rng = WorldRng(9)
    started = time.perf_counter()
    for index in range(40):
        generate_player(_spec(Position.CM, 65), ctx, rng.fork(str(index)))
    assert (time.perf_counter() - started) / 40 < 0.05  # generous tripwire: world budget is 5 s
