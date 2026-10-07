"""v1 sim tactic modules (S) and reserved stubs (R)."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, ClassVar, Literal

from pydantic import Field

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import Unit

TACTICS_SCHEMA_VERSION = 1


class BuildUp(DomainModel):
    """Build-up play module."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "kind": "S",
        "version": "S",
        "goalkeeper": "S",
        "tempo": "S",
        "passing_directness": "S",
        "width": "S",
        "patience": "S",
    }

    kind: Literal["build_up"] = "build_up"
    version: int = TACTICS_SCHEMA_VERSION
    goalkeeper: Literal["short", "mixed", "long"] = "mixed"
    tempo: Unit = 0.5
    passing_directness: Unit = 0.5
    width: Unit = 0.5
    patience: Unit = 0.5


class FinalThird(DomainModel):
    """Final-third attacking module."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "kind": "S",
        "version": "S",
        "shoot_on_sight": "S",
        "crossing_frequency": "S",
        "dribbling_freedom": "S",
        "focus": "S",
        "box_occupation": "S",
    }

    kind: Literal["final_third"] = "final_third"
    version: int = TACTICS_SCHEMA_VERSION
    shoot_on_sight: Unit = 0.5
    crossing_frequency: Unit = 0.5
    dribbling_freedom: Unit = 0.5
    focus: Literal["left", "centre", "right", "balanced"] = "balanced"
    box_occupation: Unit = 0.5


class DefensiveBlock(DomainModel):
    """Defensive block module."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "kind": "S",
        "version": "S",
        "line_height": "S",
        "compactness": "S",
        "offside_trap": "S",
        "marking": "S",
        "tackling": "S",
    }

    kind: Literal["defensive_block"] = "defensive_block"
    version: int = TACTICS_SCHEMA_VERSION
    line_height: Unit = 0.5
    compactness: Unit = 0.5
    offside_trap: Unit = 0.5
    marking: Literal["zonal", "mixed", "man"] = "mixed"
    tackling: Literal["stay_on_feet", "balanced", "aggressive"] = "balanced"


class Pressing(DomainModel):
    """Pressing module."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "kind": "S",
        "version": "S",
        "intensity": "S",
        "trigger": "S",
        "press_line": "S",
        "cover_shadow": "S",
    }

    kind: Literal["pressing"] = "pressing"
    version: int = TACTICS_SCHEMA_VERSION
    intensity: Unit = 0.5
    trigger: Literal["none", "ball_to_wide", "backpass", "loss_of_ball", "constant"] = (
        "loss_of_ball"
    )
    press_line: Unit = 0.5
    cover_shadow: Unit = 0.5


class Transitions(DomainModel):
    """Transition module."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "kind": "S",
        "version": "S",
        "on_win": "S",
        "on_loss": "S",
        "counter_press_seconds": "S",
    }

    kind: Literal["transitions"] = "transitions"
    version: int = TACTICS_SCHEMA_VERSION
    on_win: Literal["counter", "hold_shape", "slow_down"] = "hold_shape"
    on_loss: Literal["counter_press", "regroup", "drop"] = "regroup"
    counter_press_seconds: int = Field(ge=0, le=12, default=4)


class SetPieces(DomainModel):
    """Set-piece module."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "kind": "S",
        "version": "S",
        "corner_routine": "S",
        "corner_attackers": "S",
        "corner_defence": "S",
        "fk_routine": "S",
        "throw_in": "S",
    }

    kind: Literal["set_pieces"] = "set_pieces"
    version: int = TACTICS_SCHEMA_VERSION
    corner_routine: str = "default"
    corner_attackers: int = Field(ge=2, le=6, default=4)
    corner_defence: str = "default"
    fk_routine: str = "default"
    throw_in: str = "default"


class GameManagement(DomainModel):
    """Game-management module."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "kind": "S",
        "version": "S",
        "time_wasting": "S",
        "foul_tolerance": "S",
    }

    kind: Literal["game_management"] = "game_management"
    version: int = TACTICS_SCHEMA_VERSION
    time_wasting: Unit = 0.0
    foul_tolerance: Unit = 0.5


class ReservedModule(DomainModel):
    """Schema stub for modules unused by the v1 sim."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "kind": "R",
        "version": "R",
        "params": "R",
    }

    kind: Literal[
        "support_geometry",
        "gegenpress",
        "overloads",
        "rest_defence",
        "positional_zones",
        "set_piece_routines",
        "individual_tendencies",
    ]
    version: int = TACTICS_SCHEMA_VERSION
    params: Mapping[str, str | int | float | bool] = Field(default_factory=dict)


TacticModule = Annotated[
    BuildUp
    | FinalThird
    | DefensiveBlock
    | Pressing
    | Transitions
    | SetPieces
    | GameManagement
    | ReservedModule,
    Field(discriminator="kind"),
]


class ModuleKey(StrEnum):
    """Stable keys for the TeamTactics.modules map."""

    BUILD_UP = "build_up"
    FINAL_THIRD = "final_third"
    DEFENSIVE_BLOCK = "defensive_block"
    PRESSING = "pressing"
    TRANSITIONS = "transitions"
    SET_PIECES = "set_pieces"
    GAME_MANAGEMENT = "game_management"
    SUPPORT_GEOMETRY = "support_geometry"
    GEGENPRESS = "gegenpress"
    OVERLOADS = "overloads"
    REST_DEFENCE = "rest_defence"
    POSITIONAL_ZONES = "positional_zones"
    SET_PIECE_ROUTINES = "set_piece_routines"
    INDIVIDUAL_TENDENCIES = "individual_tendencies"
