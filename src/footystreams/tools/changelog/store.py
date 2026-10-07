"""Reading and writing change fragments on disk."""

from __future__ import annotations

import re
from pathlib import Path

from footystreams.tools.changelog.fragment import Fragment, parse_fragment, render_fragment

UNRELEASED = "unreleased"
RELEASED = "released"
MAX_SLUG_LENGTH = 50


class FragmentStore:
    """The `changes/` directory: `unreleased/` plus one folder per release under `released/`."""

    def __init__(self, changes_dir: Path) -> None:
        """Create a store rooted at `changes_dir`."""
        self._changes_dir = changes_dir

    @property
    def unreleased_dir(self) -> Path:
        """Where fragments for the next release live."""
        return self._changes_dir / UNRELEASED

    def unreleased(self) -> list[Fragment]:
        """Parse every unreleased fragment, ordered by id (newest last)."""
        return sorted(
            (self._read(path) for path in self._fragment_paths(self.unreleased_dir)),
            key=lambda fragment: fragment.id,
        )

    def next_id(self) -> str:
        """Return the next unused fragment id, considering unreleased and released fragments."""
        released_root = self._changes_dir / RELEASED
        paths = [*self._fragment_paths(self.unreleased_dir), *released_root.rglob("*.md")]
        ids = [int(self._read(path).id) for path in paths]
        return f"{max(ids, default=0) + 1:04d}"

    def add(self, fragment: Fragment) -> Path:
        """Write a new fragment file and return its path."""
        self.unreleased_dir.mkdir(parents=True, exist_ok=True)
        path = self.unreleased_dir / f"{fragment.id}-{_slug(fragment.summary)}.md"
        path.write_text(render_fragment(fragment), encoding="utf-8", newline="\n")
        return path

    @staticmethod
    def _fragment_paths(directory: Path) -> list[Path]:
        return sorted(directory.glob("[0-9][0-9][0-9][0-9]-*.md")) if directory.is_dir() else []

    @staticmethod
    def _read(path: Path) -> Fragment:
        return parse_fragment(path.read_text(encoding="utf-8"), source=path.name)


def _slug(summary: str) -> str:
    words = re.sub(r"[^a-z0-9]+", "-", summary.lower()).strip("-")
    return words[:MAX_SLUG_LENGTH].rstrip("-")
