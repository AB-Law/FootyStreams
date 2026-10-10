"""Extension Protocols: Narrator and related seams (stubs until M13 expands them)."""

from __future__ import annotations

from typing import Protocol

from footystreams.extensions.brief import BroadcastBrief, CommentaryLine, CrewMember


class Narrator(Protocol):
    """Turns a facts-only BroadcastBrief into studio commentary lines."""

    def narrate(
        self, brief: BroadcastBrief, speakers: tuple[CrewMember, ...]
    ) -> tuple[CommentaryLine, ...]:
        """Produce lines; must not invent clubs, scores or people absent from the brief."""
