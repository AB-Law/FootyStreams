"""Tactic presets (``data/static/tactic_presets.yaml``) as validated TeamTactics documents."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from footystreams.domain.manager import ManagerStyle
from footystreams.domain.roles import RoleCatalog
from footystreams.domain.static_tables import FormationCatalog
from footystreams.domain.tactics import Mentality, TeamTactics
from footystreams.domain.types import Duty, FormationId, Position, RoleAssignment, RoleId
from footystreams.seed.static.files import StaticDataError, YamlModel, load_model


class _PresetYaml(YamlModel):
    style: ManagerStyle
    formation: str
    mentality: Mentality
    slots: tuple[str, ...]
    modules: dict[str, dict[str, str | int | float | bool]]


class _PresetsFile(YamlModel):
    presets: dict[str, _PresetYaml]
    position_defaults: dict[Position, str]


@dataclass(frozen=True, slots=True)
class TacticPreset:
    """A named TeamTactics document and the manager style it belongs to."""

    key: str
    style: ManagerStyle
    tactics: TeamTactics


def _tactics(
    key: str, raw: _PresetYaml, roles: RoleCatalog, formations: FormationCatalog
) -> TeamTactics:
    formation = formations.formations.get(FormationId(raw.formation))
    if formation is None:
        msg = f"tactic_presets.yaml: preset {key!r} uses unknown formation {raw.formation!r}"
        raise StaticDataError(msg)
    slots = []
    for index, entry in enumerate(raw.slots):
        role_name, _, duty = entry.partition(":")
        role = roles.roles.get(RoleId(role_name))
        if role is None or Duty(duty) not in role.duties:
            msg = f"tactic_presets.yaml: preset {key!r} slot {index}: unusable role {entry!r}"
            raise StaticDataError(msg)
        if index < len(formation.slots) and role.position is not formation.slots[index].position:
            wanted = formation.slots[index].position.value
            msg = (
                f"tactic_presets.yaml: preset {key!r} slot {index} is {wanted} "
                f"but role {role_name!r} is {role.position.value}"
            )
            raise StaticDataError(msg)
        slots.append({"slot": index, "role": role_name, "duty": duty})
    modules = {name: {"kind": name, **params} for name, params in raw.modules.items()}
    try:
        return TeamTactics.model_validate(
            {
                "formation": raw.formation,
                "slots": slots,
                "mentality": raw.mentality,
                "modules": modules,
            }
        )
    except ValidationError as error:
        msg = f"tactic_presets.yaml: preset {key!r} is not a valid TeamTactics:\n{error}"
        raise StaticDataError(msg) from error


@dataclass(frozen=True, slots=True)
class PresetTables:
    """Presets by manager style plus the fallback role of each position."""

    by_style: Mapping[ManagerStyle, TacticPreset]
    default_roles: Mapping[Position, RoleAssignment]


def _default_roles(raw: _PresetsFile, roles: RoleCatalog) -> dict[Position, RoleAssignment]:
    defaults: dict[Position, RoleAssignment] = {}
    for position in Position:
        entry = raw.position_defaults.get(position)
        if entry is None:
            msg = f"tactic_presets.yaml: no position_defaults entry for {position.value}"
            raise StaticDataError(msg)
        name, _, duty = entry.partition(":")
        role = roles.roles.get(RoleId(name))
        if role is None or role.position is not position or Duty(duty) not in role.duties:
            msg = f"tactic_presets.yaml: position_defaults[{position.value}] {entry!r} is unusable"
            raise StaticDataError(msg)
        defaults[position] = RoleAssignment(role_id=RoleId(name), duty=Duty(duty))
    return defaults


def load_presets(
    roles: RoleCatalog, formations: FormationCatalog, directory: Path | None = None
) -> PresetTables:
    """Load presets keyed by manager style (exactly one per style) and the position defaults."""
    raw = load_model(_PresetsFile, "tactic_presets.yaml", directory)
    by_style: dict[ManagerStyle, TacticPreset] = {}
    for key, item in raw.presets.items():
        if item.style in by_style:
            msg = f"tactic_presets.yaml: two presets for style {item.style.value!r}"
            raise StaticDataError(msg)
        by_style[item.style] = TacticPreset(key, item.style, _tactics(key, item, roles, formations))
    missing = [style.value for style in ManagerStyle if style not in by_style]
    if missing:
        msg = f"tactic_presets.yaml: no preset for style(s) {', '.join(missing)}"
        raise StaticDataError(msg)
    return PresetTables(by_style=by_style, default_roles=_default_roles(raw, roles))
