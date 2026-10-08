"""Config overrides given as ``group.knob=value`` pairs or as a partial mapping.

``--set shot.xg_cap=0.35`` becomes ``{"shot": {"xg_cap": 0.35}}``, which ``merge_config`` lays over
a base config and validates. Values are read as YAML scalars, so ``0.35``, ``3`` and ``true`` do
what they look like.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import yaml

from footystreams.sim.config import SimConfig, merge_config

SEPARATOR = "="
PATH_SEPARATOR = "."


def nest(path: str, value: object) -> dict[str, object]:
    """``nest("a.b", 1)`` is ``{"a": {"b": 1}}``."""
    first, _, rest = path.partition(PATH_SEPARATOR)
    return {first: nest(rest, value) if rest else value}


def parse_pair(pair: str) -> dict[str, object]:
    """Read one ``path=value`` argument into a nested mapping."""
    path, found, text = pair.partition(SEPARATOR)
    if not found or not path:
        msg = f"override {pair!r} must look like group.knob=value"
        raise ValueError(msg)
    return nest(path.strip(), yaml.safe_load(text))


def _merge(into: dict[str, object], extra: Mapping[str, object]) -> None:
    for key, value in extra.items():
        if isinstance(value, Mapping):
            current = into.setdefault(key, {})
            if isinstance(current, dict):
                _merge(current, value)
                continue
        into[key] = value


def combine(overrides: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Deep-merge mappings in order; later ones win."""
    combined: dict[str, object] = {}
    for mapping in overrides:
        _merge(combined, mapping)
    return combined


def apply(base: SimConfig, overrides: Mapping[str, object]) -> SimConfig:
    """``base`` with ``overrides`` applied; a bad knob raises ``ValueError``."""
    return merge_config(base, overrides) if overrides else base
