"""The tunable knobs of ``SimConfig``: every float, found by walking the config model.

A knob is addressed by its dotted path (``shot.xg_cap``). Sensitivity and the fit change knobs by a
*multiplier* of their default, so every knob is explored on the same relative scale whatever its
units, and the config validators decide what is legal: a multiplier that builds an invalid config
is simply not a legal move. Integers and structural values (tuples, flags, names) are not knobs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from pydantic import BaseModel

from footystreams.balance import overrides
from footystreams.sim.config import SimConfig


@dataclass(frozen=True, slots=True)
class Knob:
    """One float of the config and the value it has in the base configuration."""

    path: str
    default: float


def _walk(model: BaseModel, prefix: str) -> Iterable[Knob]:
    for name in type(model).model_fields:
        value = getattr(model, name)
        path = f"{prefix}{name}"
        if isinstance(value, BaseModel):
            yield from _walk(value, f"{path}{overrides.PATH_SEPARATOR}")
        elif isinstance(value, float) and not isinstance(value, bool):
            yield Knob(path, value)


def discover(config: SimConfig) -> list[Knob]:
    """Every float knob of ``config``, in declaration order."""
    return list(_walk(config, ""))


def choose(config: SimConfig, paths: Iterable[str]) -> list[Knob]:
    """The named knobs; an unknown path (or a non-float) raises ``ValueError``."""
    known = {knob.path: knob for knob in discover(config)}
    unknown = [path for path in paths if path not in known]
    if unknown:
        msg = f"unknown or non-float knobs: {', '.join(unknown)}"
        raise ValueError(msg)
    return [known[path] for path in paths]


def with_multipliers(
    base: SimConfig, knobs: Iterable[Knob], multipliers: Mapping[str, float]
) -> SimConfig:
    """``base`` with each knob set to ``default x multiplier``; raises ``ValueError`` if illegal."""
    changes = [overrides.nest(k.path, k.default * multipliers[k.path]) for k in knobs]
    return overrides.apply(base, overrides.combine(changes))
