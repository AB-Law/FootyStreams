"""Generate a manager: style-driven philosophy, formations, specialist attributes and history."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from footystreams.domain.manager import (
    Manager,
    ManagerAttrs,
    ManagerContract,
    ManagerStint,
    ManagerStyle,
    Philosophy,
    PressProfile,
    PressTone,
    SubHabits,
    TouchlineBehaviour,
)
from footystreams.domain.person import Personality
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import ClubId, FormationId, Gender
from footystreams.domain.world import WIDER_WORLD_PREFIX
from footystreams.seed.managers.styles import StylePrototype
from footystreams.seed.people import PersonBrief, make_person
from footystreams.seed.players.context import GenerationContext
from footystreams.seed.players.mind import generate_personality

AGE_RANGE = (38, 66)
GENDER_WEIGHTS = {Gender.MALE: 88.0, Gender.FEMALE: 11.0, Gender.NONBINARY: 1.0}
PHILOSOPHY_NOISE = 0.08
ATTRIBUTE_NOISE = 6.0
MAX_FALLBACKS = 3
PREFERRED_PROFICIENCY = (85, 98)
FALLBACK_PROFICIENCY = (65, 85)
OTHER_PROFICIENCY = (30, 55)
PREFERRED_WINDOWS = (55, 60, 65, 70, 75, 80)
CARD_REACTION_RANGE = (0.4, 0.9)
FRESH_LEGS_RANGE = (0.3, 0.8)
USES_ALL_SUBS_CHANCE = 0.75
CONTRACT_YEARS = (1, 3)
STINT_COUNT = (2, 4)
STINT_YEARS = (1, 4)
MATCHES_PER_YEAR = (30, 46)
WAGE_BASE = 6_000
WIDER_WORLD_CLUBS = 40
PERCENT = 100.0
EXPERIENCE_FLOOR = 0.2  # share of matches a stint's wins can fall to at the weak end


@dataclass(frozen=True, slots=True)
class ManagerSpec:
    """What the manager generator is asked for."""

    club_id: ClubId | None
    style: ManagerStyle
    quality: int
    reputation: int
    region: str


def _unit(rng: WorldRng, centre: float, noise: float = PHILOSOPHY_NOISE) -> float:
    return rng.truncated_normal(centre, noise, 0.0, 1.0)


def _philosophy(rng: WorldRng, prototype: StylePrototype) -> Philosophy:
    centres = prototype.philosophy
    return Philosophy(
        possession_preference=_unit(rng, centres["possession_preference"]),
        directness=_unit(rng, centres["directness"]),
        pressing_intensity=_unit(rng, centres["pressing_intensity"]),
        tempo=_unit(rng, centres["tempo"]),
        width=_unit(rng, centres["width"]),
        defensive_line=_unit(rng, centres["defensive_line"]),
        risk_taking=_unit(rng, centres["risk_taking"]),
        set_piece_focus=rng.u(),
        rotation_tendency=rng.u(),
        youth_trust=rng.u(),
    )


def _formations(
    rng: WorldRng, prototype: StylePrototype, catalog_keys: tuple[str, ...]
) -> tuple[str, tuple[str, ...], dict[FormationId, int]]:
    """Preferred formation, up to three fallbacks, and proficiency in every catalog formation."""
    preferred = rng.choice_weighted(prototype.formations)
    candidates = {key: weight for key, weight in prototype.formations.items() if key != preferred}
    fallbacks: list[str] = []
    while candidates and len(fallbacks) < MAX_FALLBACKS:
        pick = rng.choice_weighted(candidates)
        fallbacks.append(pick)
        del candidates[pick]
    proficiency: dict[FormationId, int] = {}
    for key in catalog_keys:
        if key == preferred:
            band = PREFERRED_PROFICIENCY
        elif key in fallbacks:
            band = FALLBACK_PROFICIENCY
        else:
            band = OTHER_PROFICIENCY
        proficiency[FormationId(key)] = rng.randint(*band)
    return preferred, tuple(fallbacks), proficiency


def _attributes(rng: WorldRng, quality: int, deltas: dict[str, int]) -> ManagerAttrs:
    values = {
        name: max(
            1, min(100, round(quality + deltas.get(name, 0) + rng.normal(0.0, ATTRIBUTE_NOISE)))
        )
        for name in ManagerAttrs.model_fields
    }
    return ManagerAttrs(**values)


def _substitution_habits(rng: WorldRng, prototype: StylePrototype) -> SubHabits:
    ranges = prototype.substitutions
    return SubHabits(
        earliest_minute=rng.randint(*ranges.earliest_minute),
        preferred_windows=tuple(sorted(rng.shuffled(PREFERRED_WINDOWS)[:3])),
        aggressiveness=rng.uniform(*ranges.aggressiveness),
        fresh_legs_bias=rng.uniform(*FRESH_LEGS_RANGE),
        protect_lead_bias=rng.uniform(*ranges.protect_lead_bias),
        chase_game_bias=rng.uniform(*ranges.chase_game_bias),
        reacts_to_cards=rng.uniform(*CARD_REACTION_RANGE),
        uses_all_subs=rng.bernoulli(USES_ALL_SUBS_CHANCE),
    )


def _press_profile(
    rng: WorldRng, prototype: StylePrototype, personality: Personality
) -> PressProfile:
    candour = personality.media_openness / PERCENT
    return PressProfile(
        tone=PressTone(rng.choice_weighted(prototype.press_tones)),
        candour=candour,
        deflection=1.0 - candour,
        blame_tendency=personality.ego / PERCENT * rng.uniform(0.5, 1.0),
        bold_claims=personality.ego / PERCENT,
        mind_games=personality.ambition / PERCENT * rng.uniform(0.5, 1.0),
        humor=personality.humor / PERCENT,
    )


def _history(rng: WorldRng, today: dt.date) -> tuple[ManagerStint, ...]:
    stints: list[ManagerStint] = []
    end_year = today.year - rng.randint(0, 2)
    for _ in range(rng.randint(*STINT_COUNT)):
        years = rng.randint(*STINT_YEARS)
        played = years * rng.randint(*MATCHES_PER_YEAR)
        won = round(played * rng.uniform(EXPERIENCE_FLOOR, 0.5))
        drawn = round((played - won) * rng.uniform(0.2, 0.5))
        club = ClubId(f"{WIDER_WORLD_PREFIX}{rng.randint(1, WIDER_WORLD_CLUBS):03d}")
        stints.append(
            ManagerStint(
                club_id=club,
                from_date=dt.date(end_year - years, 7, 1),
                to_date=dt.date(end_year, 6, 30),
                played=played,
                won=won,
                drawn=drawn,
                lost=played - won - drawn,
            )
        )
        end_year -= years
    return tuple(reversed(stints))


def _contract(rng: WorldRng, spec: ManagerSpec, today: dt.date) -> ManagerContract | None:
    if spec.club_id is None:
        return None
    remaining = rng.randint(*CONTRACT_YEARS)
    wage = round(WAGE_BASE * (1 + (spec.reputation / 50) ** 2))
    return ManagerContract(
        club_id=spec.club_id,
        start=dt.date(today.year - rng.randint(0, 2), 7, 1),
        end=dt.date(today.year + remaining, 6, 30),
        wage_weekly=wage,
    )


def generate_manager(spec: ManagerSpec, ctx: GenerationContext, rng: WorldRng) -> Manager:
    """Build a manager whose philosophy, formations and habits follow his style."""
    prototype = ctx.tables.styles.styles[spec.style]
    specialism = rng.fork("specialism").choice(sorted(ctx.tables.styles.specialisms))
    age = rng.randint(*AGE_RANGE)
    personality = generate_personality(rng.fork("mind"), age, youth=False)
    person = make_person(
        rng.fork("person"),
        ctx,
        PersonBrief(
            kind="manager",
            age=age,
            gender=rng.fork("gender").choice_weighted(GENDER_WEIGHTS),
            region=spec.region,
            personality=personality,
            reputation=spec.reputation,
        ),
    )
    formation_keys = tuple(sorted(str(key) for key in ctx.tables.formations.formations))
    preferred, fallbacks, proficiency = _formations(
        rng.fork("formations"), prototype, formation_keys
    )
    attributes = _attributes(
        rng.fork("attributes"), spec.quality, ctx.tables.styles.specialisms[specialism]
    )
    return Manager(
        **person.model_dump(),
        style=spec.style,
        philosophy=_philosophy(rng.fork("philosophy"), prototype),
        preferred_formation=FormationId(preferred),
        fallback_formations=tuple(FormationId(key) for key in fallbacks),
        formation_proficiency=proficiency,
        flexibility=attributes.adaptability / PERCENT,
        substitution_habits=_substitution_habits(rng.fork("subs"), prototype),
        touchline_behaviour=TouchlineBehaviour(
            rng.fork("touchline").choice_weighted(prototype.touchline)
        ),
        attributes=attributes,
        press_style=_press_profile(rng.fork("press"), prototype, personality),
        contract=_contract(rng.fork("contract"), spec, ctx.today),
        career_history=_history(rng.fork("history"), ctx.today),
    )
