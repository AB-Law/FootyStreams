"""Specific exceptions raised by the simulation."""

from __future__ import annotations


class InvalidSetupError(ValueError):
    """A MatchSetup that is structurally valid but cannot be simulated (unknown formation, ...).

    Raised before the first event is produced, never mid-match; the message carries the ids.
    """


class EngineError(RuntimeError):
    """The engine broke one of its own guarantees (a bug in the simulator, not in the setup).

    Distinct from `InvalidSetupError` so callers can tell "fix the input" from "page someone".
    """
