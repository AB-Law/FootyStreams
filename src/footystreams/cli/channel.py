"""``uv run channel``: keep the VPL News desk on air, forever (or for ``--max-segments``).

The producer runs ahead of the clock: segments are scheduled back to back and a new one is made
whenever less than ``--ahead-minutes`` of airtime is queued. The viewer (``channel.html``) plays
whatever is on air right now, joining in the middle, and can go back through the last few hours.
Talk comes only from LM Studio; if it is off or slow the viewer shows a stand-by scene and the
producer retries with a growing wait.

While it runs you can ask for things (the control room on the page does the same)::

    uv run channel breaking "Seisund County sack their manager"   # on air within seconds
    uv run channel guest Jorsen                                  # interviewed next
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from footystreams.cli.channel_matches import WorldMatches
from footystreams.cli.channel_store import ChannelStore
from footystreams.cli.lm_chat import LmStudioChat
from footystreams.cli.lm_client import DEFAULT_ENDPOINT, DEFAULT_MODEL
from footystreams.extensions.show.bible import ShowBible, new_bible
from footystreams.extensions.show.breaking import clean_headline
from footystreams.extensions.show.feed import (
    KEEP_PAST_S,
    ChannelIndex,
    insert_segments,
    schedule,
    scheduled_end,
    stale_files,
    with_cast,
    with_segment,
)
from footystreams.extensions.show.models import Segment
from footystreams.extensions.show.newsroom import Newsroom
from footystreams.extensions.show.producer import ChatError, Producer, Production, ProductionError
from footystreams.extensions.show.triggers import Trigger
from footystreams.persistence.ports import NotFoundError
from footystreams.seed.static.files import StaticDataError
from footystreams.seed.world_io import WorldFileError, read_world
from footystreams.tools.paths import PROJECT_ROOT

DEFAULT_WORLD = PROJECT_ROOT / "data" / "worlds" / "default"
DEFAULT_OUT = PROJECT_ROOT / "viewer" / "replays" / "channel"
EXIT_OK, EXIT_USAGE = 0, 2
FIRST_BACKOFF_S = 5.0
MAX_BACKOFF_S = 120.0
POLL_S = 1.0
URGENT_LEAD_S = 2.0
SECONDS_PER_HOUR = 3600.0
TRIGGER_KINDS = ("breaking", "guest")


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    """How far ahead to run, how long to keep what has aired, and when to stop."""

    ahead_s: float = 600.0
    lead_s: float = 15.0
    max_segments: int | None = None
    keep_past_s: float = KEEP_PAST_S


def build_parser() -> argparse.ArgumentParser:
    """Define the channel command line."""
    parser = argparse.ArgumentParser(prog="channel", description=__doc__)
    parser.add_argument("--world", type=Path, default=DEFAULT_WORLD)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="folder the viewer reads")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="model id as shown in LM Studio")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--ahead-minutes", type=float, default=10.0, help="airtime to keep queued")
    parser.add_argument(
        "--keep-hours", type=float, default=4.0, help="how far back viewers can scroll"
    )
    parser.add_argument(
        "--lead-seconds", type=float, default=15.0, help="delay before a late segment airs"
    )
    parser.add_argument(
        "--max-segments", type=int, default=None, help="stop after this many (default: never)"
    )
    parser.add_argument("--reset", action="store_true", help="forget the bible and the feed first")
    return parser


def _say(message: str) -> None:
    """Print a log line at once, even when output is redirected to a file."""
    print(message, flush=True)


@dataclass(frozen=True, slots=True)
class Runtime:
    """The clock, the wait and the log, so the loop can be driven without real time."""

    clock: Callable[[], float] = time.time
    sleep: Callable[[float], None] = time.sleep
    log: Callable[[str], None] = _say


class Channel:
    """The loop that keeps the desk supplied with segments and answers triggers."""

    def __init__(
        self,
        producer: Producer,
        store: ChannelStore,
        config: ChannelConfig,
        runtime: Runtime | None = None,
    ) -> None:
        """Pick up where the saved bible and feed left off, or start a new show."""
        self.producer = producer
        self.store = store
        self.config = config
        self.runtime = runtime or Runtime()
        self.bible: ShowBible = store.load_bible() or new_bible(
            producer.room.world.created_in_world
        )
        self.index: ChannelIndex = store.load_index()
        self.backoff = FIRST_BACKOFF_S

    def _save(self, updated: ChannelIndex, bible: ShowBible, segments: Sequence[Segment]) -> None:
        """Write the new segments, then the index that lists them, then the bible."""
        updated = with_cast(updated, self.producer.cast)
        for segment in segments:
            self.store.save_segment(segment)
        self.store.save_index(updated)
        self.store.save_bible(bible)
        self.store.delete(stale_files(self.index, updated))
        self.index, self.bible = updated, bible

    def _publish(self, production: Production) -> None:
        now = self.runtime.clock()
        segment = schedule(self.index, production.segment, now, self.config.lead_s)
        updated = with_segment(self.index, segment, now, self.config.keep_past_s)
        self._save(updated, production.bible, [segment])
        self.backoff = FIRST_BACKOFF_S
        queued = (scheduled_end(updated) - now) / 60
        self.runtime.log(
            f"channel: #{segment.number} {segment.kind.value}: {segment.title} "
            f"({segment.duration_s:.0f}s, {production.attempts} try); {queued:.1f} min queued"
        )

    def _breaking(self, text: str) -> None:
        headline = clean_headline(text)
        if not headline:
            self.runtime.log("channel: a breaking-news trigger had no usable headline")
            return
        made = self.producer.breaking(self.bible, headline)
        now = self.runtime.clock()
        updated, scheduled = insert_segments(
            self.index, made.segments, now, URGENT_LEAD_S, cut=True
        )
        self._save(updated, made.bible, scheduled)
        self.runtime.log(f"channel: BREAKING NEWS on air: {headline}")
        if made.note:
            self.runtime.log(f"channel: {made.note}")

    def _guest(self, text: str) -> None:
        bible, name = self.producer.request_guest(self.bible, text)
        if not name:
            self.runtime.log(f"channel: nobody in this world matches {text!r}")
            return
        self.store.save_bible(bible)
        self.bible = bible
        try:
            production = self.producer.produce(bible)
        except ChatError as error:
            self.runtime.log(f"channel: {name} is booked, but the model is not answering ({error})")
            return
        except ProductionError as error:
            self.runtime.log(f"channel: {error}")
            self.bible = self.producer.failed(bible, error)
            self.store.save_bible(self.bible)
            return
        now = self.runtime.clock()
        updated, scheduled = insert_segments(
            self.index, [production.segment], now, self.config.lead_s, cut=False
        )
        self._save(updated, production.bible, scheduled)
        self.runtime.log(f"channel: {name} is joining the desk after the current segment")

    def _triggers(self) -> None:
        """Handle whatever has been asked for since last time."""
        for path in self.store.pending_triggers():
            try:
                trigger = self.store.read_trigger(path)
            except ValueError as error:
                self.runtime.log(f"channel: ignoring {path.name}: {error}")
                path.unlink(missing_ok=True)
                continue
            path.unlink(missing_ok=True)
            if trigger.kind == "breaking":
                self._breaking(trigger.text)
            else:
                self._guest(trigger.text)

    def _step(self) -> bool:
        """Answer any triggers, then make one segment if the queue needs it."""
        self._triggers()
        ahead = scheduled_end(self.index) - self.runtime.clock()
        if ahead >= self.config.ahead_s:
            self.runtime.sleep(min(POLL_S, ahead - self.config.ahead_s + 1.0))
            return False
        try:
            production = self.producer.produce(self.bible)
        except ChatError as error:
            self.runtime.log(
                f"channel: the model is not answering ({error}); retrying in {self.backoff:.0f}s"
            )
            self.runtime.sleep(self.backoff)
            self.backoff = min(self.backoff * 2, MAX_BACKOFF_S)
            return False
        except ProductionError as error:
            self.runtime.log(f"channel: {error}")
            self.bible = self.producer.failed(self.bible, error)
            self.store.save_bible(self.bible)
            return False
        self._publish(production)
        return True

    def run(self) -> int:
        """Keep going until ``config.max_segments`` segments are made, or for ever."""
        made = 0
        while self.config.max_segments is None or made < self.config.max_segments:
            made += self._step()
        return EXIT_OK


def _run(arguments: argparse.Namespace) -> int:
    world = read_world(arguments.world)
    store = ChannelStore(arguments.out)
    if arguments.reset:
        store.reset()
    chat = LmStudioChat(arguments.model, arguments.endpoint, arguments.temperature)
    room = Newsroom(world)
    store.save_directory(room.directory())
    producer = Producer(room, chat, WorldMatches(arguments.world))
    config = ChannelConfig(
        arguments.ahead_minutes * 60,
        arguments.lead_seconds,
        arguments.max_segments,
        arguments.keep_hours * SECONDS_PER_HOUR,
    )
    names = ", ".join(member.name for member in producer.cast)
    _say(f"channel: on air from {arguments.out} with {names}; model {arguments.model}")
    return Channel(producer, store, config).run()


def _send_trigger(argv: list[str]) -> int:
    """``channel breaking "..."`` or ``channel guest NAME``: leave a request for the channel."""
    parser = argparse.ArgumentParser(prog=f"channel {argv[0]}")
    parser.add_argument("text", nargs="+", help="the headline, or the guest's name")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="folder the channel uses")
    arguments = parser.parse_args(argv[1:])
    try:
        trigger = Trigger(kind=argv[0], text=" ".join(arguments.text))  # type: ignore[arg-type]
    except ValueError as error:
        print(f"channel: error: {error}", file=sys.stderr)
        return EXIT_USAGE
    path = ChannelStore(arguments.out).write_trigger(trigger)
    _say(f"channel: asked for {trigger.kind} ({path.name}); it airs within a few seconds")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """CLI entry; returns a process exit code."""
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in TRIGGER_KINDS:
        return _send_trigger(args)
    arguments = build_parser().parse_args(args)
    try:
        return _run(arguments)
    except (ValueError, WorldFileError, StaticDataError, NotFoundError, OSError) as error:
        print(f"channel: error: {error}", file=sys.stderr)
        return EXIT_USAGE
    except KeyboardInterrupt:
        print("channel: off air")
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
