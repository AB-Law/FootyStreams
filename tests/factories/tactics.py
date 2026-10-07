"""Builders for TeamTactics."""

from __future__ import annotations

from footystreams.domain.tactics import Mentality, SlotAssignment, TeamTactics
from footystreams.domain.tactics.modules.v1 import BuildUp, ModuleKey, Pressing
from footystreams.domain.types import Duty, FormationId, RoleId


def make_team_tactics() -> TeamTactics:
    """Build a balanced 4-3-3 with eleven slots."""
    slots = tuple(
        SlotAssignment(
            slot=index, role=RoleId("poacher" if index == 10 else "box_to_box"), duty=Duty.SUPPORT
        )
        for index in range(11)
    )
    return TeamTactics(
        formation=FormationId("433"),
        slots=slots,
        mentality=Mentality.BALANCED,
        modules={
            ModuleKey.BUILD_UP: BuildUp(),
            ModuleKey.PRESSING: Pressing(intensity=0.6),
        },
    )
