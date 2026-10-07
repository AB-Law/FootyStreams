"""Plan and generate a club's squad, calibrated so the best XI hits the archetype's strength."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace

from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.domain.squad_strength import squad_strength
from footystreams.domain.static_tables import Formation
from footystreams.domain.tactics import TeamTactics
from footystreams.domain.types import ClubId, NationId, Position
from footystreams.seed.clubs.archetypes import ClubArchetype, SquadSpec
from footystreams.seed.players.context import GenerationContext, Geography
from footystreams.seed.players.generator import PlayerSpec, generate_player

MAX_CALIBRATION_ATTEMPTS = 5
YOUNG_AGE_LIMIT = 20
YOUNG_PENALTY_PER_YEAR = 2.5
OLD_AGE_LIMIT = 32
OLD_PENALTY_PER_YEAR = 1.2
YOUNG_SQUAD_AGE_SHIFT = 2.5
YOUNG_SQUAD_YOUTH_BOOST = 4
MIN_TARGET, MAX_TARGET = 30, 95


@dataclass(frozen=True, slots=True)
class SquadBrief:
    """What the squad generator is asked for."""

    club_id: ClubId
    region: str
    reputation: int
    archetype: ClubArchetype
    tactics: TeamTactics
    nationalities: tuple[NationId, ...] = ()


@dataclass(frozen=True, slots=True)
class CalibrationTarget:
    """The team rating the club should reach, and how close is close enough."""

    rating: float
    tolerance: float


def _age_adjustment(age: int) -> float:
    if age <= YOUNG_AGE_LIMIT:
        return -(YOUNG_AGE_LIMIT + 1 - age) * YOUNG_PENALTY_PER_YEAR
    if age > OLD_AGE_LIMIT:
        return -(age - OLD_AGE_LIMIT) * OLD_PENALTY_PER_YEAR
    return 0.0


def _senior_age(rng: WorldRng, spec: SquadSpec, position: Position, *, young_squad: bool) -> int:
    mean = spec.age_mean - (YOUNG_SQUAD_AGE_SHIFT if young_squad else 0.0)
    if position is Position.GK:
        mean += spec.goalkeeper_age_bonus
    low, high = spec.age_range
    return round(rng.truncated_normal(mean, spec.age_deviation, low, high))


def _depth_drop(rng: WorldRng, spec: SquadSpec, depth: int, starters: int) -> float:
    if depth < starters:
        return rng.normal(0.0, spec.starter_noise)
    bounds = spec.second_choice_drop if depth == starters else spec.deep_drop
    return -rng.uniform(*bounds)


def senior_specs(
    rng: WorldRng, brief: SquadBrief, formation: Formation, quality: float, spec: SquadSpec
) -> list[PlayerSpec]:
    """One PlayerSpec per senior slot of the template, abilities shaped by depth and age."""
    needed = Counter(formation.positions())
    specs: list[PlayerSpec] = []
    for position, count in spec_items(spec):
        for depth in range(count):
            age = _senior_age(rng, spec, position, young_squad=brief.archetype.young_squad)
            drop = _depth_drop(rng, spec, depth, needed[position])
            target = round(quality + drop + _age_adjustment(age))
            specs.append(
                PlayerSpec(
                    position=position,
                    age=age,
                    target_ability=max(MIN_TARGET, min(MAX_TARGET, target)),
                    club_id=brief.club_id,
                    region=brief.region,
                    club_reputation=brief.reputation,
                    potential_bonus=brief.archetype.academy_bonus,
                    nationality=_nationality_at(brief, len(specs)),
                )
            )
    return specs


def _nationality_at(brief: SquadBrief, index: int) -> NationId | None:
    return brief.nationalities[index] if index < len(brief.nationalities) else None


def nationality_plan(
    rng: WorldRng, geography: Geography, spec: SquadSpec, count: int
) -> tuple[NationId, ...]:
    """Nationalities of a senior squad: a capped home contingent, the rest from several nations."""
    home = min(rng.randint(*spec.home_players), count)
    foreign = sorted(geography.foreign, key=lambda nation: nation.id)
    chosen = rng.shuffled(foreign)[: rng.randint(*spec.foreign_nations)]
    taken: Counter[NationId] = Counter()
    plan = [geography.home.id] * home
    while len(plan) < count:
        nation = rng.choice(chosen)
        if taken[nation.id] < spec.max_per_foreign_nation:
            taken[nation.id] += 1
            plan.append(nation.id)
    return tuple(rng.shuffled(plan))


def spec_items(spec: SquadSpec) -> list[tuple[Position, int]]:
    """Template entries in a stable order (position enum order)."""
    return [
        (position, spec.senior_template[position])
        for position in Position
        if position in spec.senior_template
    ]


def youth_specs(rng: WorldRng, brief: SquadBrief, spec: SquadSpec) -> list[PlayerSpec]:
    """Academy prospects: young, modest now, high potential (more so at academy-minded clubs)."""
    boost = YOUNG_SQUAD_YOUTH_BOOST if brief.archetype.young_squad else 0
    return [
        PlayerSpec(
            position=position,
            age=rng.randint(*spec.youth_age_range),
            target_ability=rng.randint(*spec.youth_ability) + boost,
            club_id=brief.club_id,
            region=brief.region,
            club_reputation=brief.reputation,
            youth=True,
            potential_bonus=brief.archetype.academy_bonus + boost,
        )
        for position in spec.youth_positions
    ]


def _attempt(
    ctx: GenerationContext, rng: WorldRng, brief: SquadBrief, quality: float
) -> tuple[list[Player], list[Player]]:
    squad_spec = ctx.tables.clubs.squad
    formation = ctx.tables.formations.formations[brief.tactics.formation]
    seniors = [
        generate_player(spec, ctx, rng.fork(f"senior:{index}"))
        for index, spec in enumerate(
            senior_specs(rng.fork("plan"), brief, formation, quality, squad_spec)
        )
    ]
    youth = [
        generate_player(spec, ctx, rng.fork(f"youth:{index}"))
        for index, spec in enumerate(youth_specs(rng.fork("youth-plan"), brief, squad_spec))
    ]
    return seniors, youth


def generate_squad(
    ctx: GenerationContext, rng: WorldRng, brief: SquadBrief, target: CalibrationTarget
) -> tuple[list[Player], list[Player]]:
    """Seniors and youth for a club; retries with a corrected quality until the XI rating fits.

    A discarded attempt is rolled back (names, ids) so only the accepted squad leaves a trace.
    """
    squad_spec = ctx.tables.clubs.squad
    total = sum(squad_spec.senior_template.values())
    brief = replace(
        brief,
        nationalities=nationality_plan(rng.fork("nationality"), ctx.geography, squad_spec, total),
    )
    quality = target.rating
    for attempt in range(MAX_CALIBRATION_ATTEMPTS):
        checkpoint = ctx.checkpoint()
        seniors, youth = _attempt(ctx, rng.fork(f"attempt:{attempt}"), brief, quality)
        error = target.rating - squad_strength(seniors, brief.tactics, ctx.tables.roles)
        if abs(error) <= target.tolerance or attempt == MAX_CALIBRATION_ATTEMPTS - 1:
            return seniors, youth
        ctx.restore(checkpoint)
        quality += error
    msg = "calibration loop exited without a squad"
    raise RuntimeError(msg)
