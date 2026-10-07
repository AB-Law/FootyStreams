"""Role catalog contract (M2 ``roles.yaml`` must conform to this shape)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from pydantic import Field, model_validator

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.types import Duty, Position, RoleId, Unit


class RoleDutySpec(DomainModel):
    """Weights and spatial/utility hints for one role+duty pair.

    ``attr_weights`` drive M1 CA / role ratings. ``offset_*`` and
    ``utility_biases`` are the M2/M4 sim contract (positioning + decision
    biases); ratings ignore them until the sim consumes the catalog.
    """

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "attr_weights": "S",
        "offset_x": "S",
        "offset_y": "S",
        "utility_biases": "S",
    }

    attr_weights: Mapping[str, float] = Field(min_length=1)
    # Normalised pitch offsets from the role's default slot (0 = none).
    offset_x: Unit = 0.0
    offset_y: Unit = 0.0
    # Named decision biases for the sim (e.g. "shoot", "dribble", "cross").
    utility_biases: Mapping[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _weights_positive(self) -> RoleDutySpec:
        if any(weight < 0 for weight in self.attr_weights.values()):
            msg = "attr_weights must be non-negative"
            raise ValueError(msg)
        if sum(self.attr_weights.values()) <= 0:
            msg = "attr_weights must sum to a positive value"
            raise ValueError(msg)
        return self


class RoleDefinition(DomainModel):
    """One named role with duties and the position used for competence scaling."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "role_id": "S",
        "position": "S",
        "duties": "S",
    }

    role_id: RoleId
    position: Position
    duties: Mapping[Duty, RoleDutySpec] = Field(min_length=1)


class RoleCatalog(DomainModel):
    """Pure in-memory role table; YAML loading arrives in M2."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"roles": "S"}

    roles: Mapping[RoleId, RoleDefinition] = Field(min_length=1)

    def get(self, role_id: RoleId) -> RoleDefinition | None:
        """Return the role definition or ``None`` if unknown."""
        return self.roles.get(role_id)
