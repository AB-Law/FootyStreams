"""A sweep that can be stopped and resumed: one JSON line per finished knob.

The file starts with a header (the settings the run was made with, and the base run's metric values
and noise) followed by one line per knob. Resuming checks that the settings are exactly those of the
file, so results from different matches, seeds or nudges can never be mixed, and skips the knobs
already recorded. Every line is flushed as it is written: stopping loses at most the knob in flight.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from footystreams.balance.knobs import Knob
from footystreams.balance.sensitivity import Sensitivity


class StateMismatchError(ValueError):
    """The state file was written by a run with different settings."""


@dataclass(frozen=True, slots=True)
class Header:
    """What the run was, and its base measurements."""

    settings: Mapping[str, object]
    base_values: Mapping[str, float]
    noise: Mapping[str, float]


def _line(document: Mapping[str, object]) -> str:
    return json.dumps(document, sort_keys=True) + "\n"


def write_header(path: Path, header: Header) -> None:
    """Start the file; refuses to overwrite an existing one."""
    document = {
        "header": {"settings": header.settings, "base": header.base_values, "noise": header.noise}
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(_line(document))


def append(path: Path, item: Sensitivity) -> None:
    """Add one finished knob and flush it to disk."""
    document = {"knob": item.knob.path, "default": item.knob.default, "effects": item.effects}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_line(document))
        handle.flush()


def load(path: Path, settings: Mapping[str, object]) -> tuple[Header, dict[str, Sensitivity]]:
    """Read a state file made with exactly ``settings``; returns its header and finished knobs."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows or "header" not in rows[0]:
        msg = f"{path} is not a balance state file"
        raise StateMismatchError(msg)
    raw = rows[0]["header"]
    if raw["settings"] != json.loads(json.dumps(settings)):
        msg = (
            f"{path} was made with different settings; delete it or pick another --state.\n"
            f"file:    {raw['settings']}\nnow:     {dict(settings)}"
        )
        raise StateMismatchError(msg)
    finished = {
        row["knob"]: Sensitivity(Knob(row["knob"], row["default"]), row["effects"])
        for row in rows[1:]
    }
    return Header(raw["settings"], raw["base"], raw["noise"]), finished
