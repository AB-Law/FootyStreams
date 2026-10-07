"""Load ``roles.yaml`` into the domain ``RoleCatalog`` (expanding multi-position roles)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from footystreams.domain.attributes import (
    GoalkeepingAttrs,
    HiddenAttrs,
    MentalAttrs,
    PhysicalAttrs,
    TechnicalAttrs,
)
from footystreams.domain.roles import RoleCatalog, RoleDefinition, RoleDutySpec
from footystreams.domain.types import Duty, Position, RoleId
from footystreams.seed.static.files import StaticDataError, YamlModel, load_model

ATTRIBUTE_NAMES: frozenset[str] = frozenset(
    name
    for group in (TechnicalAttrs, MentalAttrs, PhysicalAttrs, GoalkeepingAttrs, HiddenAttrs)
    for name in group.model_fields
)


class _DutyProfile(YamlModel):
    weights: dict[str, float] = Field(default_factory=dict)
    offset_x: float = 0.0
    utility_biases: dict[str, float] = Field(default_factory=dict)


class _RoleYaml(YamlModel):
    positions: tuple[Position, ...]
    duties: tuple[Duty, ...]
    weights: dict[str, float]
    adjust_by_duty: bool = True


class _RolesFile(YamlModel):
    duty_profiles: dict[Duty, _DutyProfile]
    roles: dict[str, _RoleYaml]


def role_id_for(base: str, position: Position, *, multi_position: bool) -> RoleId:
    """Id of a role at a position: plain when the role has one position, suffixed otherwise."""
    return RoleId(f"{base}_{position.value.lower()}" if multi_position else base)


def _spec(role: _RoleYaml, profile: _DutyProfile) -> RoleDutySpec:
    weights = dict(role.weights)
    if role.adjust_by_duty:
        for name, extra in profile.weights.items():
            weights[name] = weights.get(name, 0.0) + extra
    return RoleDutySpec(
        attr_weights=weights, offset_x=profile.offset_x, utility_biases=profile.utility_biases
    )


def _check_role(base: str, role: _RoleYaml, raw: _RolesFile) -> None:
    undefined = sorted(duty.value for duty in role.duties if duty not in raw.duty_profiles)
    if undefined:
        msg = f"roles.yaml: role {base!r} uses undefined duty {', '.join(undefined)}"
        raise StaticDataError(msg)
    names = set(role.weights)
    for duty in role.duties:
        names |= set(raw.duty_profiles[duty].weights)
    unknown = sorted(names - ATTRIBUTE_NAMES)
    if unknown:
        msg = f"roles.yaml: role {base!r} weights unknown attributes: {', '.join(unknown)}"
        raise StaticDataError(msg)


def load_roles(directory: Path | None = None) -> RoleCatalog:
    """Build the catalog; unknown attributes, duties or duplicate expanded ids are errors."""
    raw = load_model(_RolesFile, "roles.yaml", directory)
    roles: dict[RoleId, RoleDefinition] = {}
    for base, role in raw.roles.items():
        _check_role(base, role, raw)
        multi = len(role.positions) > 1
        for position in role.positions:
            role_id = role_id_for(base, position, multi_position=multi)
            if role_id in roles:
                msg = f"roles.yaml: duplicate expanded role id {role_id!r}"
                raise StaticDataError(msg)
            duties = {duty: _spec(role, raw.duty_profiles[duty]) for duty in role.duties}
            roles[role_id] = RoleDefinition(role_id=role_id, position=position, duties=duties)
    return RoleCatalog(roles=roles)
