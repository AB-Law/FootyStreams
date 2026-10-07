"""Tactic module models and discriminated union."""

from footystreams.domain.tactics.modules.v1 import (
    TACTICS_SCHEMA_VERSION,
    ModuleKey,
    TacticModule,
)

__all__ = ["TACTICS_SCHEMA_VERSION", "ModuleKey", "TacticModule"]
