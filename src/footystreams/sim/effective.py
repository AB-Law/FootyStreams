"""Effective skills: a player's attributes after the named, bounded match-day modifiers.

`eff(a) = base(a) x form x morale x sharpness x position competence x role familiarity x day form`
(docs/design/02 section 3). Every modifier is bounded and the result is clamped to
[0.55 x base, 1.15 x base], so no single number can blow up an outcome. Fatigue and mood join in M6.
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.snapshot import PlayerSnapshot
from footystreams.domain.types import Position, RoleId
from footystreams.sim.rng import SimRng

FORM_SWING = 0.08
MORALE_SWING = 0.06
MORALE_MENTAL_WEIGHT = 1.5
MORALE_PHYSICAL_WEIGHT = 0.5
SHARPNESS_FLOOR = 0.97
SHARPNESS_RANGE = 0.03
COMPETENCE_FLOOR = 0.55
COMPETENCE_RANGE = 0.45
ROLE_FLOOR = 0.97
ROLE_RANGE = 0.03
DAY_SIGMA_BASE = 0.012
DAY_SIGMA_RANGE = 0.05
LOWER_BOUND = 0.55
UPPER_BOUND = 1.15
DEFAULT_COMPETENCE = 20
DEFAULT_FAMILIARITY = 50
PERCENT = 100.0


@dataclass(frozen=True, slots=True)
class Skills:
    """The effective attributes the simulation reads (floats on the 1-100 scale)."""

    finishing: float
    long_shots: float
    heading: float
    first_touch: float
    dribbling: float
    short_passing: float
    long_passing: float
    crossing: float
    tackling: float
    marking: float
    set_piece_delivery: float
    penalty_taking: float
    vision: float
    decisions: float
    composure: float
    anticipation: float
    positioning: float
    off_ball_movement: float
    work_rate: float
    aggression: float
    bravery: float
    flair: float
    pace: float
    acceleration: float
    stamina: float
    strength: float
    agility: float
    balance: float
    jumping_reach: float
    natural_fitness: float
    handling: float
    shot_stopping: float
    aerial_command: float
    distribution: float
    one_on_ones: float
    sweeping: float
    dirtiness: float
    injury_proneness: float
    big_match: float


@dataclass(frozen=True, slots=True)
class Multipliers:
    """The per-group multipliers applied to a player's base attributes."""

    technical: float
    mental: float
    physical: float


def day_form_multiplier(consistency: int, rng: SimRng) -> float:
    """Return this match's form-of-the-day multiplier (one draw per player per match).

    Spread shrinks with the hidden `consistency` attribute: steady players vary by about 1%,
    erratic ones by up to about 6%.
    """
    sigma = DAY_SIGMA_BASE + DAY_SIGMA_RANGE * (1.0 - consistency / PERCENT)
    return 1.0 + sigma * rng.gauss()


def multipliers(
    snapshot: PlayerSnapshot, slot_position: Position, role: RoleId, day_form: float
) -> Multipliers:
    """Combine form, morale, sharpness, competence, role familiarity and day form per group."""
    form = 1.0 + FORM_SWING * (snapshot.form - 0.5)
    morale = MORALE_SWING * (snapshot.morale - 0.5)
    sharpness = SHARPNESS_FLOOR + SHARPNESS_RANGE * snapshot.match_sharpness
    competence = snapshot.position_competence.get(slot_position, DEFAULT_COMPETENCE)
    suitability = COMPETENCE_FLOOR + COMPETENCE_RANGE * competence / PERCENT
    familiarity = snapshot.role_familiarity.get(role, DEFAULT_FAMILIARITY)
    role_fit = ROLE_FLOOR + ROLE_RANGE * familiarity / PERCENT
    common = form * suitability * role_fit * day_form
    return Multipliers(
        technical=common * sharpness,
        mental=common * sharpness * (1.0 + MORALE_MENTAL_WEIGHT * morale),
        physical=common * (1.0 + MORALE_PHYSICAL_WEIGHT * morale),
    )


def _bounded(base: int, multiplier: float) -> float:
    return max(LOWER_BOUND * base, min(UPPER_BOUND * base, base * multiplier))


def build_skills(snapshot: PlayerSnapshot, mult: Multipliers) -> Skills:
    """Build effective skills for a snapshot under the given multipliers."""
    t, m, p, k, h = (
        snapshot.technical,
        snapshot.mental,
        snapshot.physical,
        snapshot.goalkeeping,
        snapshot.hidden,
    )
    tech, ment, phys = mult.technical, mult.mental, mult.physical
    return Skills(
        finishing=_bounded(t.finishing, tech),
        long_shots=_bounded(t.long_shots, tech),
        heading=_bounded(t.heading, tech),
        first_touch=_bounded(t.first_touch, tech),
        dribbling=_bounded(t.dribbling, tech),
        short_passing=_bounded(t.short_passing, tech),
        long_passing=_bounded(t.long_passing, tech),
        crossing=_bounded(t.crossing, tech),
        tackling=_bounded(t.tackling, tech),
        marking=_bounded(t.marking, tech),
        set_piece_delivery=_bounded(t.set_piece_delivery, tech),
        penalty_taking=_bounded(t.penalty_taking, tech),
        vision=_bounded(m.vision, ment),
        decisions=_bounded(m.decisions, ment),
        composure=_bounded(m.composure, ment),
        anticipation=_bounded(m.anticipation, ment),
        positioning=_bounded(m.positioning, ment),
        off_ball_movement=_bounded(m.off_ball_movement, ment),
        work_rate=_bounded(m.work_rate, ment),
        aggression=_bounded(m.aggression, ment),
        bravery=_bounded(m.bravery, ment),
        flair=_bounded(m.flair, ment),
        pace=_bounded(p.pace, phys),
        acceleration=_bounded(p.acceleration, phys),
        stamina=_bounded(p.stamina, phys),
        strength=_bounded(p.strength, phys),
        agility=_bounded(p.agility, phys),
        balance=_bounded(p.balance, phys),
        jumping_reach=_bounded(p.jumping_reach, phys),
        natural_fitness=float(p.natural_fitness),
        handling=_bounded(k.handling, tech),
        shot_stopping=_bounded(k.shot_stopping, tech),
        aerial_command=_bounded(k.aerial_command, tech),
        distribution=_bounded(k.distribution, tech),
        one_on_ones=_bounded(k.one_on_ones, tech),
        sweeping=_bounded(k.sweeping, tech),
        dirtiness=float(h.dirtiness),
        injury_proneness=float(h.injury_proneness),
        big_match=float(h.big_match),
    )
