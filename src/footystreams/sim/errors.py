"""Specific exceptions raised by the simulation."""

from __future__ import annotations


class InvalidSetupError(ValueError):
    """A MatchSetup that is structurally valid but cannot be simulated (unknown formation, ...).

    Raised before the first event is produced, never mid-match; the message carries the ids.
    """
