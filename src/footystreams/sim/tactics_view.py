"""TacticsView: the flat, typed numbers the simulation reads from a team's tactics.

Sim components never touch `TeamTactics` storage. The view applies the module defaults when a
module is absent and folds mentality and the manager's philosophy into a few unit-range numbers,
so new tactic modules can be added without changing the sim (docs/design/02 section 2).
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.match import TeamSheet
from footystreams.domain.tactics import Mentality, ModuleKey, module_or_default
from footystreams.domain.tactics.modules.v1 import (
    BuildUp,
    DefensiveBlock,
    FinalThird,
    GameManagement,
    Pressing,
)

_MENTALITY_LEVEL = {
    Mentality.ULTRA_DEFENSIVE: -1.0,
    Mentality.DEFENSIVE: -2 / 3,
    Mentality.CAUTIOUS: -1 / 3,
    Mentality.BALANCED: 0.0,
    Mentality.POSITIVE: 1 / 3,
    Mentality.ATTACKING: 2 / 3,
    Mentality.ALL_OUT: 1.0,
}


_TACKLE_AGGRESSION = {"stay_on_feet": 0.8, "balanced": 1.0, "aggressive": 1.25}


@dataclass(frozen=True, slots=True)
class TacticsView:
    """Unit-range tactical numbers for one team (0 = least, 1 = most unless noted)."""

    mentality: float  # -1 ultra defensive .. +1 all out
    tempo: float
    directness: float
    width: float
    patience: float
    line_height: float
    compactness: float
    press_intensity: float
    shoot_on_sight: float
    crossing_frequency: float
    dribbling_freedom: float
    risk_taking: float
    time_wasting: float
    foul_tolerance: float
    offside_trap: float
    tackle_aggression: (
        float  # multiplier on foul-worthy contact: 0.8 stay on feet .. 1.25 aggressive
    )


def build_view(sheet: TeamSheet) -> TacticsView:
    """Build the tactics view for a sheet, using module defaults for absent modules."""
    tactics = sheet.tactics
    build_up = _module(sheet, ModuleKey.BUILD_UP, BuildUp)
    block = _module(sheet, ModuleKey.DEFENSIVE_BLOCK, DefensiveBlock)
    pressing = _module(sheet, ModuleKey.PRESSING, Pressing)
    final_third = _module(sheet, ModuleKey.FINAL_THIRD, FinalThird)
    management = _module(sheet, ModuleKey.GAME_MANAGEMENT, GameManagement)
    return TacticsView(
        mentality=_MENTALITY_LEVEL[tactics.mentality],
        tempo=build_up.tempo,
        directness=build_up.passing_directness,
        width=build_up.width,
        patience=build_up.patience,
        line_height=block.line_height,
        compactness=block.compactness,
        press_intensity=pressing.intensity,
        shoot_on_sight=final_third.shoot_on_sight,
        crossing_frequency=final_third.crossing_frequency,
        dribbling_freedom=final_third.dribbling_freedom,
        risk_taking=sheet.manager.philosophy.risk_taking,
        time_wasting=management.time_wasting,
        foul_tolerance=management.foul_tolerance,
        offside_trap=block.offside_trap,
        tackle_aggression=_TACKLE_AGGRESSION[block.tackling],
    )


def _module[ModuleT](sheet: TeamSheet, key: ModuleKey, expected: type[ModuleT]) -> ModuleT:
    found = module_or_default(sheet.tactics, key)
    if not isinstance(found, expected):
        msg = f"module {key} on {sheet.club.id} is a {type(found).__name__}, expected {expected}"
        raise TypeError(msg)
    return found
