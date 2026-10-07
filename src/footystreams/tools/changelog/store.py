"""Reading and writing change fragments on disk."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from footystreams.tools.changelog.fragment import Fragment, parse_fragment, render_fragment

UNRELEASED = "unreleased"
RELEASED = "released"
RELEASE_FILE = "release.json"
MAX_SLUG_LENGTH = 50
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class Release:
    """A published version and the fragments it contains."""

    version: str
    date: date
    fragments: tuple[Fragment, ...]


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
        return _read_all(self._fragment_paths(self.unreleased_dir))

    def releases(self) -> list[Release]:
        """Every published release, newest version first."""
        found = []
        for folder in (self._changes_dir / RELEASED).glob("*/"):
            published = json.loads((folder / RELEASE_FILE).read_text(encoding="utf-8"))
            fragments = tuple(_read_all(self._fragment_paths(folder)))
            found.append(Release(folder.name, date.fromisoformat(published["date"]), fragments))
        return sorted(found, key=lambda release: _version_key(release.version), reverse=True)

    def next_id(self) -> str:
        """Return the next unused fragment id, considering unreleased and released fragments."""
        released = (self._changes_dir / RELEASED).rglob("[0-9][0-9][0-9][0-9]-*.md")
        paths = [*self._fragment_paths(self.unreleased_dir), *released]
        ids = [int(fragment.id) for fragment in _read_all(paths)]
        return f"{max(ids, default=0) + 1:04d}"

    def add(self, fragment: Fragment) -> Path:
        """Write a new fragment file and return its path."""
        self.unreleased_dir.mkdir(parents=True, exist_ok=True)
        path = self.unreleased_dir / f"{fragment.id}-{_slug(fragment.summary)}.md"
        path.write_text(render_fragment(fragment), encoding="utf-8", newline="\n")
        return path

    def publish(self, version: str, released_on: date) -> Release:
        """Move all unreleased fragments into `released/<version>/` and return the release."""
        if not SEMVER.match(version):
            raise ValueError(f"version {version!r} is not MAJOR.MINOR.PATCH")
        folder = self._changes_dir / RELEASED / version
        paths = self._fragment_paths(self.unreleased_dir)
        if folder.exists() or not paths:
            reason = "already exists" if folder.exists() else "there are no unreleased fragments"
            raise ValueError(f"cannot release {version}: {reason}")
        folder.mkdir(parents=True)
        for path in paths:
            path.rename(folder / path.name)
        (folder / RELEASE_FILE).write_text(
            json.dumps({"version": version, "date": released_on.isoformat()}) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return Release(version, released_on, tuple(_read_all(self._fragment_paths(folder))))

    @staticmethod
    def _fragment_paths(directory: Path) -> list[Path]:
        return sorted(directory.glob("[0-9][0-9][0-9][0-9]-*.md")) if directory.is_dir() else []


def _read_all(paths: list[Path]) -> list[Fragment]:
    fragments = [parse_fragment(path.read_text(encoding="utf-8"), path.name) for path in paths]
    return sorted(fragments, key=lambda fragment: fragment.id)


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _slug(summary: str) -> str:
    words = re.sub(r"[^a-z0-9]+", "-", summary.lower()).strip("-")
    return words[:MAX_SLUG_LENGTH].rstrip("-")
