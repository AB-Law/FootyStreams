"""Training quality: how well a club's facilities and coaches develop each attribute group."""

from __future__ import annotations

from collections.abc import Sequence

from footystreams.domain.club import Club
from footystreams.domain.staff import StaffMember, StaffRole
from footystreams.league.development import GROUPS, Conditions
from footystreams.league.development_config import ProgressionConfig

NEUTRAL_COACHING = 50
LEVEL_SCALE = 100.0
GROUP_COACHES: dict[str, tuple[StaffRole, ...]] = {
    "technical": (StaffRole.FIRST_TEAM_COACH, StaffRole.ASSISTANT_MANAGER),
    "mental": (StaffRole.FIRST_TEAM_COACH, StaffRole.ASSISTANT_MANAGER),
    "physical": (StaffRole.FITNESS_COACH,),
    "goalkeeping": (StaffRole.GOALKEEPING_COACH,),
}
COACHING_ATTRIBUTE = {
    "technical": "coaching_technical",
    "mental": "coaching_mental",
    "physical": "coaching_physical",
    "goalkeeping": "coaching_technical",
}


def _coaching(staff: Sequence[StaffMember], group: str) -> float:
    skills = [
        int(getattr(member.attrs, COACHING_ATTRIBUTE[group]))
        for member in staff
        if member.role in GROUP_COACHES[group]
    ]
    return sum(skills) / len(skills) if skills else NEUTRAL_COACHING


def training_conditions(
    club: Club | None, staff: Sequence[StaffMember], playing_time: float, config: ProgressionConfig
) -> Conditions:
    """Quality of training per group from the facility level and the relevant coaches.

    A player with no club (a free agent) trains on his own: the neutral coaching level and the
    lowest facility level.
    """
    facility = club.facilities.training / LEVEL_SCALE if club else 0.0
    weight = config.facility_weight
    quality = {
        group: weight * facility + (1 - weight) * _coaching(staff, group) / LEVEL_SCALE
        for group in GROUPS
    }
    return Conditions(training=quality, playing_time=playing_time)
