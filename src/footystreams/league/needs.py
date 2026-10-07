"""What a club needs: shortages by position group and weak spots in the first eleven."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from footystreams.domain.player import Player
from footystreams.domain.types import Position
from footystreams.league.transfer_config import NeedsConfig

GROUPS: Mapping[str, frozenset[Position]] = {
    "GK": frozenset({Position.GK}),
    "DEF": frozenset({Position.CB, Position.RB, Position.LB, Position.RWB, Position.LWB}),
    "MID": frozenset({Position.DM, Position.CM, Position.AM, Position.LM, Position.RM}),
    "FWD": frozenset({Position.ST, Position.SS, Position.RW, Position.LW}),
}
MAX_QUALITY_URGENCY = 0.6
QUALITY_SCALE = 20.0  # ability points below the club's mean at which a weak spot is most urgent


@dataclass(frozen=True, slots=True)
class Need:
    """A position group a club wants to strengthen."""

    group: str
    urgency: float  # 0..1; 1.0 means the group is short of players
    min_quality: int  # the ability a signing should have
    positions: frozenset[Position]


def group_of(position: Position) -> str:
    """The position group a position belongs to."""
    return next(name for name, members in GROUPS.items() if position in members)


def analyse(
    squad: Sequence[Player], formation: Sequence[Position], config: NeedsConfig
) -> list[Need]:
    """Needs of a club, most urgent first; ties by group name so the order is stable."""
    mean = sum(p.ability_current for p in squad) / len(squad) if squad else 0.0
    needs = []
    for group, members in GROUPS.items():
        in_group = sorted(
            (p for p in squad if p.primary_position in members), key=lambda p: -p.ability_current
        )
        starters = sum(1 for position in formation if position in members)
        weakest = in_group[starters - 1].ability_current if len(in_group) >= starters > 0 else 0
        short = len(in_group) < config.position_minimum[group]
        gap = max(0.0, (mean - weakest) / QUALITY_SCALE) if starters else 0.0
        urgency = 1.0 if short else min(MAX_QUALITY_URGENCY, gap)
        if urgency > 0.0:
            needs.append(Need(group, urgency, weakest + config.upgrade_margin, members))
    return sorted(needs, key=lambda need: (-need.urgency, need.group))
