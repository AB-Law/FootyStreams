"""A club's default tactics: the manager's preset, re-cut for his formation and philosophy."""

from __future__ import annotations

from collections.abc import Mapping

from footystreams.domain.manager import Manager, Philosophy
from footystreams.domain.tactics import ModuleKey, SlotAssignment, TacticModule, TeamTactics
from footystreams.domain.tactics.modules.v1 import BuildUp, DefensiveBlock, Pressing
from footystreams.domain.types import UNIT_DECIMALS, Position
from footystreams.seed.static.presets import TacticPreset
from footystreams.seed.static.tables import StaticTables

PHILOSOPHY_WEIGHT = 0.5  # how far the manager's own sliders pull the preset towards them


def _blend(preset_value: float, philosophy_value: float) -> float:
    """Weighted mean, rounded like a Unit: model_copy skips validation, so we must do it here."""
    mixed = (1 - PHILOSOPHY_WEIGHT) * preset_value + PHILOSOPHY_WEIGHT * philosophy_value
    return round(mixed, UNIT_DECIMALS)


def _slots_for(
    preset: TacticPreset, positions: tuple[Position, ...], tables: StaticTables
) -> tuple[SlotAssignment, ...]:
    """Reuse the preset's role for each position in order; fall back to the position default."""
    preset_formation = tables.formations.formations[preset.tactics.formation]
    pool: dict[Position, list[SlotAssignment]] = {}
    for shape, slot in zip(preset_formation.slots, preset.tactics.slots, strict=True):
        pool.setdefault(shape.position, []).append(slot)
    slots: list[SlotAssignment] = []
    for index, position in enumerate(positions):
        available = pool.get(position)
        if available:
            chosen = available.pop(0)
            slots.append(SlotAssignment(slot=index, role=chosen.role, duty=chosen.duty))
        else:
            default = tables.presets.default_roles[position]
            slots.append(SlotAssignment(slot=index, role=default.role_id, duty=default.duty))
    return tuple(slots)


def _adjusted_modules(
    modules: Mapping[ModuleKey, TacticModule], philosophy: Philosophy
) -> dict[ModuleKey, TacticModule]:
    """Pull the preset's tempo, directness, width, line height and press towards the manager."""
    adjusted = dict(modules)
    build_up = modules.get(ModuleKey.BUILD_UP)
    if isinstance(build_up, BuildUp):
        adjusted[ModuleKey.BUILD_UP] = build_up.model_copy(
            update={
                "tempo": _blend(build_up.tempo, philosophy.tempo),
                "passing_directness": _blend(build_up.passing_directness, philosophy.directness),
                "width": _blend(build_up.width, philosophy.width),
            }
        )
    block = modules.get(ModuleKey.DEFENSIVE_BLOCK)
    if isinstance(block, DefensiveBlock):
        adjusted[ModuleKey.DEFENSIVE_BLOCK] = block.model_copy(
            update={"line_height": _blend(block.line_height, philosophy.defensive_line)}
        )
    pressing = modules.get(ModuleKey.PRESSING)
    if isinstance(pressing, Pressing):
        adjusted[ModuleKey.PRESSING] = pressing.model_copy(
            update={"intensity": _blend(pressing.intensity, philosophy.pressing_intensity)}
        )
    return adjusted


def default_tactics(manager: Manager, tables: StaticTables) -> TeamTactics:
    """Tactics in the manager's preferred formation, shaped by his philosophy."""
    preset = tables.presets.by_style[manager.style]
    formation = tables.formations.formations[manager.preferred_formation]
    return preset.tactics.model_copy(
        update={
            "formation": manager.preferred_formation,
            "slots": _slots_for(preset, formation.positions(), tables),
            "modules": _adjusted_modules(preset.tactics.modules, manager.philosophy),
        }
    )
