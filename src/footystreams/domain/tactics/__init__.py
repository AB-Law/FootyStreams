"""Versioned TeamTactics package (core + module registry)."""

from footystreams.domain.tactics.core import Mentality, SlotAssignment, TeamTactics
from footystreams.domain.tactics.modules import ModuleKey, TacticModule
from footystreams.domain.tactics.registry import module_or_default

__all__ = [
    "Mentality",
    "ModuleKey",
    "SlotAssignment",
    "TacticModule",
    "TeamTactics",
    "module_or_default",
]
