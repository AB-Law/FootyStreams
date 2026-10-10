"""Builders for the show: a newsroom over the seed world, fake matches and fake language models."""

from __future__ import annotations

import json
from functools import cache

from footystreams.domain.match import MatchSetup
from footystreams.events.summary import MatchSummary
from footystreams.extensions.show.bible import ShowBible, new_bible
from footystreams.extensions.show.newsroom import Newsroom
from footystreams.extensions.show.producer import ChatError
from footystreams.league.clock import read_date
from footystreams.league.friendly import build_friendly_setup
from footystreams.sim import SimConfig, run_match
from footystreams.sim.tables import tables_from_catalog
from tests.factories.league_db import make_league_db
from tests.factories.league_run import make_engine
from tests.factories.world import make_world

LINES = 8
OPENERS = (
    "The desk has a proper football story to tell",
    "Nobody at this table will ever agree",
    "There is a lot of character in that club",
    "This is exactly what the supporters talk about",
    "I would not bet against that",
    "Someone should write all of this down",
)
ENDINGS = (
    "and we like it that way",
    "for years and years to come",
    "before we forget how it went",
    "every single week of the season",
    "whatever anybody says on the radio",
    "and that is the whole point of the show",
)
WORDS = tuple(f"{opener} {ending}" for opener in OPENERS for ending in ENDINGS)


@cache
def newsroom() -> Newsroom:
    """A newsroom over the seed world, built once."""
    return Newsroom(make_world(1))


def fresh_bible() -> ShowBible:
    """A bible for a show that has just started."""
    return new_bible(newsroom().world.created_in_world)


@cache
def real_match(home_id: str, away_id: str, seed: int) -> tuple[MatchSetup, MatchSummary]:
    """A friendly between two clubs of the seed world, really simulated."""
    factory = make_league_db(1)
    engine = make_engine(1)
    with factory() as uow:
        setup = build_friendly_setup(uow, home_id, away_id, engine, read_date(uow))  # type: ignore[arg-type]
        referee = uow.referees.require(setup.referee_id)
        tables = tables_from_catalog(engine.tables.formations)
    return setup, run_match(setup, seed, SimConfig(), tables, referee).summary


class FakePrepared:
    """A prepared match backed by a real, cached simulation."""

    def __init__(self, home_id: str, away_id: str) -> None:
        """Remember the two clubs."""
        self.home_id, self.away_id = home_id, away_id

    @property
    def setup(self) -> MatchSetup:
        """The real setup."""
        return real_match(self.home_id, self.away_id, 1)[0]

    def play(self, seed: int) -> MatchSummary:
        """The real summary for ``seed``."""
        return real_match(self.home_id, self.away_id, seed)[1]


class FakeMatches:
    """A match source that plays the seed world's clubs for real."""

    def prepare(self, home_id: str, away_id: str) -> FakePrepared:
        """Set up a fixture."""
        return FakePrepared(home_id, away_id)


class EchoChat:
    """A language model that always answers with a valid reply for whatever it is asked."""

    def __init__(self) -> None:
        """Start with no calls recorded."""
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        """Read the hosts from the prompt and write a line for each in turn."""
        self.calls.append((system, user))
        payload = json.loads(user.split("\n\nYour previous reply", maxsplit=1)[0])
        hosts = [host["id"] for host in payload["hosts"]]
        offset = (len(self.calls) - 1) * LINES % len(WORDS)
        lines = [
            {
                "speaker_id": hosts[index % len(hosts)],
                "text": WORDS[(offset + index) % len(WORDS)] + ".",
            }
            for index in range(LINES)
        ]
        reply: dict[str, object] = {"lines": lines, "memories": [], "predictions": []}
        if payload["segment"]["asks_for_predictions"]:
            reply["predictions"] = [
                {"host_id": host, "pick": ("home", "draw", "away")[number % 3]}
                for number, host in enumerate(hosts)
            ]
        reply["memories"] = [
            {
                "host_id": hosts[0],
                "kind": "running_joke",
                "text": "The desk keeps arguing about the car park.",
            }
        ]
        return json.dumps(reply)


class ScriptedChat:
    """A language model that gives the replies it was handed, in order; an exception is raised."""

    def __init__(self, *replies: str | Exception) -> None:
        """Queue the replies."""
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        """Pop the next reply."""
        self.calls.append((system, user))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def chat_error(message: str = "down") -> ChatError:
    """A ``ChatError`` for scripting an outage."""
    return ChatError(message)
