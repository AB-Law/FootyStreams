"""The result type of every invariant check."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Violation:
    """One broken invariant.

    Attributes:
        code: Catalogue id such as "M04" (match) or "W03" (world); see the testing strategy doc.
        message: What is wrong, in one sentence.
        subject: Id of the offending thing (event id, player id, club id), if there is one.
    """

    code: str
    message: str
    subject: str | None = None

    def __str__(self) -> str:
        """Render as `[CODE] message (subject)`."""
        suffix = f" ({self.subject})" if self.subject else ""
        return f"[{self.code}] {self.message}{suffix}"


def format_violations(violations: Iterable[Violation]) -> str:
    """Render violations one per line, sorted so the output is stable."""
    return "\n".join(str(violation) for violation in sorted(violations))
