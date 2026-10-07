"""Minimal RoleCatalog matching the M1 contract shape."""

from __future__ import annotations

from footystreams.domain.roles import RoleCatalog, RoleDefinition, RoleDutySpec
from footystreams.domain.types import Duty, Position, RoleId


def make_role_catalog() -> RoleCatalog:
    """Tiny catalog with a poacher and a keeper role for tests."""
    poacher = RoleDefinition(
        role_id=RoleId("poacher"),
        position=Position.ST,
        duties={
            Duty.ATTACK: RoleDutySpec(
                attr_weights={
                    "finishing": 3.0,
                    "composure": 2.0,
                    "off_ball_movement": 2.0,
                    "pace": 1.0,
                }
            ),
            Duty.SUPPORT: RoleDutySpec(
                attr_weights={
                    "finishing": 2.0,
                    "short_passing": 2.0,
                    "composure": 1.0,
                }
            ),
        },
    )
    keeper = RoleDefinition(
        role_id=RoleId("sweeper_keeper"),
        position=Position.GK,
        duties={
            Duty.SUPPORT: RoleDutySpec(
                attr_weights={
                    "shot_stopping": 3.0,
                    "handling": 2.0,
                    "sweeping": 1.0,
                }
            ),
        },
    )
    return RoleCatalog(roles={poacher.role_id: poacher, keeper.role_id: keeper})
