"""Generate one coherent player: archetype, spiky attributes, positions, mind, body and bio."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from footystreams.domain.attributes import HiddenAttrs
from footystreams.domain.development import TrainingPlan
from footystreams.domain.person import Person, Personality
from footystreams.domain.player import CareerStint, Player, PlayerStatus, SquadStatus
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import (
    ClubId,
    Gender,
    NationId,
    Position,
    PreferredFoot,
    RoleAssignment,
)
from footystreams.domain.world import WIDER_WORLD_PREFIX
from footystreams.seed.people import PersonBrief, make_person
from footystreams.seed.players.attributes import AttributeBrief, AttributeSet, generate_attributes
from footystreams.seed.players.body import foot_and_weak_foot, height_and_weight
from footystreams.seed.players.condition import StartingCondition, starting_condition
from footystreams.seed.players.context import GenerationContext
from footystreams.seed.players.contract import market_value_of
from footystreams.seed.players.mind import generate_hidden, generate_personality
from footystreams.seed.players.positions import (
    choose_traits,
    position_competence,
    preferred_roles,
    role_familiarity,
)

REPUTATION_ABILITY_WEIGHT = 0.8
REPUTATION_CLUB_WEIGHT = 0.2
REPUTATION_NOISE = 4.0
TRAINING_INTENSITY_RANGE = (0.4, 0.7)
WIDER_WORLD_CLUB_POOL = 40
ADULT_AGE = 21
MAX_PRIOR_STINTS = 2
STINT_YEARS_RANGE = (1, 4)
APPEARANCES_PER_YEAR = (12, 36)
GOALS_PER_APPEARANCE = {
    Position.ST: 0.45, Position.SS: 0.35, Position.AM: 0.22, Position.RW: 0.25, Position.LW: 0.25,
}  # fmt: skip
DEFAULT_GOALS_PER_APPEARANCE = 0.05
GROWTH_BY_AGE = (  # (up to and including age, (min, max) potential growth)
    (20, (8, 25)), (23, (4, 14)), (26, (1, 6)), (29, (0, 3)), (99, (0, 0)),
)  # fmt: skip
YOUTH_POTENTIAL_NOISE = 4.0
PA_CAP = 100


@dataclass(frozen=True, slots=True)
class PlayerSpec:
    """What the player generator is asked for."""

    position: Position
    age: int
    target_ability: int
    club_id: ClubId | None
    region: str
    club_reputation: int
    youth: bool = False
    potential_bonus: int = 0
    nationality: NationId | None = None


@dataclass(frozen=True, slots=True)
class _Parts:
    """Everything drawn for a player before the final model is assembled."""

    personality: Personality
    hidden: HiddenAttrs
    skills: AttributeSet
    competence: dict[Position, int]
    preferred: tuple[RoleAssignment, ...]
    foot: PreferredFoot
    weak_foot: int
    body: tuple[int, int]
    condition: StartingCondition


def potential_for(rng: WorldRng, ability: int, age: int, bonus: int) -> int:
    """Potential ability: current plus age-dependent headroom, never above 100."""
    low, high = next(growth for limit, growth in GROWTH_BY_AGE if age <= limit)
    growth = rng.randint(low, high) + bonus
    if age < ADULT_AGE:
        growth += round(rng.normal(0.0, YOUTH_POTENTIAL_NOISE))
    return max(ability, min(PA_CAP, ability + max(growth, 0)))


def _reputation(rng: WorldRng, ability: int, club_reputation: int) -> int:
    base = REPUTATION_ABILITY_WEIGHT * ability + REPUTATION_CLUB_WEIGHT * club_reputation
    return max(0, min(100, round(base + rng.normal(0.0, REPUTATION_NOISE))))


def prior_stints(rng: WorldRng, spec: PlayerSpec, today: dt.date) -> tuple[CareerStint, ...]:
    """Plausible back-history at clubs outside the league (ids are reserved ``clb_wd...``)."""
    if spec.age < ADULT_AGE or spec.club_id is None:
        return ()
    stints: list[CareerStint] = []
    end_year = today.year - rng.randint(0, 2)
    rate = GOALS_PER_APPEARANCE.get(spec.position, DEFAULT_GOALS_PER_APPEARANCE)
    for _ in range(rng.randint(0, MAX_PRIOR_STINTS)):
        years = rng.randint(*STINT_YEARS_RANGE)
        appearances = years * rng.randint(*APPEARANCES_PER_YEAR)
        club = ClubId(f"{WIDER_WORLD_PREFIX}{rng.randint(1, WIDER_WORLD_CLUB_POOL):03d}")
        stints.append(
            CareerStint(
                club_id=club,
                from_date=dt.date(end_year - years, 7, 1),
                to_date=dt.date(end_year, 6, 30),
                apps=appearances,
                goals=round(appearances * rate),
            )
        )
        end_year -= years
    return tuple(reversed(stints))


def _draw_parts(spec: PlayerSpec, ctx: GenerationContext, rng: WorldRng) -> tuple[_Parts, str]:
    tables = ctx.tables
    archetype_key = rng.fork("archetype").choice_weighted(
        tables.archetypes.for_position(spec.position)
    )
    archetype = tables.archetypes.archetypes[archetype_key]
    mind = rng.fork("mind")
    personality = generate_personality(mind, spec.age, youth=spec.youth)
    hidden = generate_hidden(mind, personality)
    competence = position_competence(
        rng.fork("positions"),
        tables.archetypes,
        spec.position,
        hidden.versatility,
        youth=spec.youth,
    )
    brief = AttributeBrief(archetype, competence, spec.target_ability)
    foot, weak_foot = foot_and_weak_foot(rng.fork("foot"))
    parts = _Parts(
        personality=personality,
        hidden=hidden,
        skills=generate_attributes(rng.fork("skills"), tables, brief),
        competence=competence,
        preferred=preferred_roles(tables.roles, archetype),
        foot=foot,
        weak_foot=weak_foot,
        body=height_and_weight(rng.fork("body"), archetype),
        condition=starting_condition(rng.fork("condition"), tables.injuries, ctx.today),
    )
    return parts, archetype_key


def generate_player(spec: PlayerSpec, ctx: GenerationContext, rng: WorldRng) -> Player:
    """Build a valid Player. He has no contract yet; the club generator signs him."""
    parts, archetype_key = _draw_parts(spec, ctx, rng)
    archetype = ctx.tables.archetypes.archetypes[archetype_key]
    ability = parts.skills.ability
    person = make_person(
        rng.fork("person"),
        ctx,
        PersonBrief(
            kind="player",
            age=spec.age,
            gender=Gender.MALE,
            region=spec.region,
            personality=parts.personality,
            reputation=_reputation(rng.fork("reputation"), ability, spec.club_reputation),
            nationality=spec.nationality,
        ),
    )
    player = _assemble(person, spec, parts, rng, ctx.today)
    traits = choose_traits(rng.fork("traits"), ctx.tables.traits, archetype)
    familiarity = role_familiarity(
        rng.fork("familiarity"), ctx.tables.roles, parts.competence, parts.preferred
    )
    player = player.model_copy(update={"traits": traits, "role_familiarity": familiarity})
    return player.model_copy(update={"market_value": market_value_of(player, ctx.today)})


def _assemble(
    person: Person, spec: PlayerSpec, parts: _Parts, rng: WorldRng, today: dt.date
) -> Player:
    skills = parts.skills
    return Player(
        **person.model_dump(),
        height_cm=parts.body[0],
        weight_kg=parts.body[1],
        preferred_foot=parts.foot,
        weak_foot=parts.weak_foot,
        position_competence=parts.competence,
        primary_position=spec.position,
        preferred_roles=parts.preferred,
        technical=skills.technical,
        mental=skills.mental,
        physical=skills.physical,
        goalkeeping=skills.goalkeeping,
        hidden=parts.hidden,
        ability_current=skills.ability,
        ability_potential=potential_for(
            rng.fork("potential"), skills.ability, spec.age, spec.potential_bonus
        ),
        form=parts.condition.form,
        morale=parts.condition.morale,
        fitness=parts.condition.fitness,
        fatigue=parts.condition.fatigue,
        match_sharpness=parts.condition.match_sharpness,
        current_injury=parts.condition.injury,
        career_history=prior_stints(rng.fork("career"), spec, today),
        training=TrainingPlan(intensity=rng.fork("training").uniform(*TRAINING_INTENSITY_RANGE)),
        status=PlayerStatus.ACTIVE if spec.club_id else PlayerStatus.FREE_AGENT,
        squad_status=_squad_status(spec),
        is_youth=spec.youth,
    )


def _squad_status(spec: PlayerSpec) -> SquadStatus:
    if spec.club_id is None:
        return SquadStatus.FREE_AGENT
    return SquadStatus.YOUTH if spec.youth else SquadStatus.FIRST_TEAM
