"""Generate club staff: coaches, physios, scouts and analysts whose attributes fit the role."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from footystreams.domain.contract import Contract, SquadRole
from footystreams.domain.rng import WorldRng
from footystreams.domain.staff import StaffAttrs, StaffMember, StaffRole
from footystreams.domain.types import ClubId, Gender
from footystreams.seed.people import PersonBrief, make_person
from footystreams.seed.players.context import GenerationContext
from footystreams.seed.players.mind import generate_personality

STAFF_AGE_RANGE = (28, 62)
GENDER_WEIGHTS = {Gender.MALE: 70.0, Gender.FEMALE: 25.0, Gender.NONBINARY: 5.0}
QUALITY_NOISE = 8.0
ATTRIBUTE_NOISE = 6.0
OFF_ROLE_PENALTY = 18
ON_ROLE_BONUS = 14
CONTRACT_YEARS = (1, 3)
WAGE_BASE = 300
WAGE_QUALITY_SCALE = 0.9
# The standard backroom team of one club: role -> how many.
BACKROOM: dict[StaffRole, int] = {
    StaffRole.ASSISTANT_MANAGER: 1,
    StaffRole.FIRST_TEAM_COACH: 1,
    StaffRole.GOALKEEPING_COACH: 1,
    StaffRole.FITNESS_COACH: 1,
    StaffRole.PHYSIO: 2,
    StaffRole.SCOUT: 2,
    StaffRole.ANALYST: 1,
}
# Attributes a role is expected to be strong in (everything else sits below the quality level).
ROLE_FOCUS: dict[StaffRole, tuple[str, ...]] = {
    StaffRole.ASSISTANT_MANAGER: ("tactical_input", "coaching_mental", "coaching_technical"),
    StaffRole.FIRST_TEAM_COACH: ("coaching_technical", "coaching_mental", "tactical_input"),
    StaffRole.GOALKEEPING_COACH: ("coaching_technical", "coaching_mental"),
    StaffRole.FITNESS_COACH: ("coaching_physical", "injury_prevention"),
    StaffRole.PHYSIO: ("injury_treatment", "injury_prevention"),
    StaffRole.SCOUT: ("scouting_judgement", "scouting_network"),
    StaffRole.ANALYST: ("tactical_input", "scouting_judgement"),
    StaffRole.YOUTH_COACH: ("coaching_technical", "coaching_mental", "coaching_physical"),
}


@dataclass(frozen=True, slots=True)
class StaffSpec:
    """What the staff generator is asked for."""

    club_id: ClubId
    role: StaffRole
    club_quality: int
    region: str


def _attrs(rng: WorldRng, role: StaffRole, quality: int) -> StaffAttrs:
    focus = ROLE_FOCUS[role]
    values = {}
    for name in StaffAttrs.model_fields:
        shift = ON_ROLE_BONUS if name in focus else -OFF_ROLE_PENALTY
        values[name] = max(1, min(100, round(quality + shift + rng.normal(0.0, ATTRIBUTE_NOISE))))
    return StaffAttrs(**values)


def generate_staff_member(spec: StaffSpec, ctx: GenerationContext, rng: WorldRng) -> StaffMember:
    """Build one staff member with a role-shaped attribute set and a modest contract."""
    quality = max(
        1, min(100, round(spec.club_quality + rng.fork("quality").normal(0.0, QUALITY_NOISE)))
    )
    age = rng.randint(*STAFF_AGE_RANGE)
    person = make_person(
        rng.fork("person"),
        ctx,
        PersonBrief(
            kind="staff",
            age=age,
            gender=rng.fork("gender").choice_weighted(GENDER_WEIGHTS),
            region=spec.region,
            personality=generate_personality(rng.fork("mind"), age, youth=False),
            reputation=quality,
        ),
    )
    years = rng.randint(*CONTRACT_YEARS)
    contract = Contract(
        club_id=spec.club_id,
        start=dt.date(ctx.today.year, 7, 1),
        end=dt.date(ctx.today.year + years, 6, 30),
        wage_weekly=round(WAGE_BASE + WAGE_QUALITY_SCALE * quality * quality),
        squad_role=SquadRole.BACKUP,
    )
    return StaffMember(
        **person.model_dump(),
        club_id=spec.club_id,
        role=spec.role,
        quality=quality,
        attrs=_attrs(rng.fork("attrs"), spec.role, quality),
        contract=contract,
    )


def generate_backroom(
    club_id: ClubId, club_quality: int, region: str, ctx: GenerationContext, rng: WorldRng
) -> tuple[StaffMember, ...]:
    """The standard backroom team of one club (nine people)."""
    members: list[StaffMember] = []
    for role, count in BACKROOM.items():
        for index in range(count):
            spec = StaffSpec(club_id, role, club_quality, region)
            members.append(generate_staff_member(spec, ctx, rng.fork(f"{role.value}:{index}")))
    return tuple(members)
