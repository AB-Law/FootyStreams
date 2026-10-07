"""Helpers for looking up tactic modules by key."""

from __future__ import annotations

from footystreams.domain.tactics.core import TeamTactics
from footystreams.domain.tactics.modules.v1 import (
    BuildUp,
    DefensiveBlock,
    FinalThird,
    GameManagement,
    ModuleKey,
    Pressing,
    SetPieces,
    TacticModule,
    Transitions,
)

_DEFAULTS: dict[ModuleKey, TacticModule] = {
    ModuleKey.BUILD_UP: BuildUp(),
    ModuleKey.FINAL_THIRD: FinalThird(),
    ModuleKey.DEFENSIVE_BLOCK: DefensiveBlock(),
    ModuleKey.PRESSING: Pressing(),
    ModuleKey.TRANSITIONS: Transitions(),
    ModuleKey.SET_PIECES: SetPieces(),
    ModuleKey.GAME_MANAGEMENT: GameManagement(),
}


def module_or_default(tactics: TeamTactics, key: ModuleKey) -> TacticModule:
    """Return the module from tactics, or the v1 default when absent."""
    found = tactics.modules.get(key)
    if found is not None:
        return found
    default = _DEFAULTS.get(key)
    if default is None:
        msg = f"no default for module {key}"
        raise KeyError(msg)
    return default
