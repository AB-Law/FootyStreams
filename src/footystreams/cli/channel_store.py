"""Files for the channel: bible, feed index, segments and triggers (impure: disk)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from footystreams.extensions.show.bible import ShowBible
from footystreams.extensions.show.feed import ChannelIndex
from footystreams.extensions.show.models import Segment
from footystreams.extensions.show.triggers import Trigger, parse_trigger

BIBLE_FILE = "bible.json"
INDEX_FILE = "index.json"
DIRECTORY_FILE = "directory.json"
TRIGGER_DIR = "triggers"
REPLACE_TRIES = 5
REPLACE_WAIT_S = 0.05


def atomic_write(path: Path, text: str) -> None:
    """Write ``text`` so a reader sees the old file or the new one, never half of it.

    On Windows a file that a web server has open cannot be replaced, so a few retries are made.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    for attempt in range(REPLACE_TRIES):
        try:
            temporary.replace(path)
        except PermissionError:
            if attempt == REPLACE_TRIES - 1:
                raise
            time.sleep(REPLACE_WAIT_S)
        else:
            return


class ChannelStore:
    """Reads and writes everything the channel keeps in one folder."""

    def __init__(self, directory: Path) -> None:
        """Use ``directory`` (created on the first write)."""
        self.directory = directory

    def load_bible(self) -> ShowBible | None:
        """The saved bible, or None for a show that has never run here."""
        path = self.directory / BIBLE_FILE
        return (
            ShowBible.model_validate_json(path.read_text(encoding="utf-8"))
            if path.is_file()
            else None
        )

    def save_bible(self, bible: ShowBible) -> None:
        """Save the bible."""
        atomic_write(self.directory / BIBLE_FILE, bible.model_dump_json(indent=1) + "\n")

    def load_index(self) -> ChannelIndex:
        """The saved feed, or an empty one."""
        path = self.directory / INDEX_FILE
        if not path.is_file():
            return ChannelIndex()
        return ChannelIndex.model_validate_json(path.read_text(encoding="utf-8"))

    def save_index(self, index: ChannelIndex) -> None:
        """Publish the feed; the viewer polls this file."""
        atomic_write(self.directory / INDEX_FILE, index.model_dump_json() + "\n")

    def save_segment(self, segment: Segment) -> None:
        """Write a segment file, before the index lists it."""
        atomic_write(self.directory / f"{segment.id}.json", segment.model_dump_json() + "\n")

    def save_directory(self, people: list[dict[str, str]]) -> None:
        """Write who could be asked on as a guest, for the control room's suggestions."""
        atomic_write(self.directory / DIRECTORY_FILE, json.dumps({"people": people}) + "\n")

    def delete(self, files: list[str]) -> None:
        """Remove segment files that have dropped out of the feed."""
        for name in files:
            (self.directory / name).unlink(missing_ok=True)

    def write_trigger(self, trigger: Trigger) -> Path:
        """Ask the running producer for something; it picks the file up within a second or so."""
        path = self.directory / TRIGGER_DIR / f"{time.time_ns()}.json"
        atomic_write(path, trigger.model_dump_json() + "\n")
        return path

    def pending_triggers(self) -> list[Path]:
        """Trigger files waiting to be handled, oldest first."""
        return sorted((self.directory / TRIGGER_DIR).glob("*.json"))

    def read_trigger(self, path: Path) -> Trigger:
        """Parse a trigger file; ``ValueError`` if it is not one."""
        return parse_trigger(path.read_text(encoding="utf-8"))

    def reset(self) -> None:
        """Forget everything: the bible, the feed, every segment and any waiting triggers."""
        waiting = self.directory.glob(f"{TRIGGER_DIR}/*.json")
        for path in [*self.directory.glob("*.json"), *waiting]:
            path.unlink()
