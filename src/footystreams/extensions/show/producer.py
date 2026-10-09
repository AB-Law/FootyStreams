"""Making one segment: plan it, gather its facts, ask the model, check the reply, remember it."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from footystreams.domain.match import MatchSetup
from footystreams.events.summary import MatchSummary
from footystreams.extensions.show.bible import GuestRequest, ShowBible
from footystreams.extensions.show.breaking import breaking_brief
from footystreams.extensions.show.breaks import break_segment, stinger_segment
from footystreams.extensions.show.facts import (
    banter_brief,
    club_history_brief,
    manager_story_brief,
    player_story_brief,
    table_brief,
)
from footystreams.extensions.show.facts_interview import guest_member, interview_brief
from footystreams.extensions.show.facts_match import preview_brief, recap_brief
from footystreams.extensions.show.feed import aftermath, build_segment, with_aftermath
from footystreams.extensions.show.memory import text_of
from footystreams.extensions.show.models import CastMember, Segment, SegmentKind
from footystreams.extensions.show.newsroom import Newsroom
from footystreams.extensions.show.plan import Plan, Roster, advance, next_plan
from footystreams.extensions.show.prompt import MAX_LINES, MIN_LINES, Prompt, build_prompt
from footystreams.extensions.show.remember import Aired, aired_segment
from footystreams.extensions.show.reply import (
    Reply,
    ReplyError,
    ReplyRules,
    names_in,
    numbers_in,
    parse_reply,
)
from footystreams.extensions.show.schedule import match_seed
from footystreams.extensions.show.segment_brief import SegmentBrief
from footystreams.extensions.show.textutil import words
from footystreams.extensions.show.triggers import resolve_guest

ATTEMPTS = 3
MAX_FAILURES = 3


class ChatError(RuntimeError):
    """The language model could not be reached or gave no answer."""


class ChatModel(Protocol):
    """Anything that turns a system and a user message into the model's reply text."""

    def complete(self, system: str, user: str) -> str:
        """Return the reply, or raise ``ChatError``."""


class PreparedMatch(Protocol):
    """A fixture set up to be played."""

    @property
    def setup(self) -> MatchSetup:
        """The two teams and everything the simulator needs."""

    def play(self, seed: int) -> MatchSummary:
        """Simulate the match and return its summary."""


class MatchSource(Protocol):
    """Where matches come from: the world, through the simulator."""

    def prepare(self, home_id: str, away_id: str) -> PreparedMatch:
        """Set up a fixture between two clubs."""


class ProductionError(RuntimeError):
    """A segment could not be made; the show tries again, or moves on after repeated failures."""

    def __init__(self, message: str, plan: Plan) -> None:
        """Keep the plan that failed, so the show can decide whether to skip it."""
        super().__init__(message)
        self.plan = plan


@dataclass(frozen=True, slots=True)
class Production:
    """A finished segment and the bible as it stands once the segment has aired."""

    segment: Segment
    bible: ShowBible
    attempts: int


@dataclass(frozen=True, slots=True)
class Breaking:
    """The segments for a breaking-news trigger: the flash, then the hosts react if they could."""

    segments: tuple[Segment, ...]
    bible: ShowBible
    note: str = ""


@dataclass(frozen=True, slots=True)
class Material:
    """What a talking segment is made from: the brief and everyone who may speak in it."""

    brief: SegmentBrief
    speakers: tuple[CastMember, ...]
    guest: CastMember | None = None


class Producer:
    """Makes the show one segment at a time."""

    def __init__(self, room: Newsroom, chat: ChatModel, matches: MatchSource) -> None:
        """Set up the desk, the rundown and the checks from the world."""
        self.room = room
        self.chat = chat
        self.matches = matches
        self.roster = Roster.from_world(room.world)
        self.cast: tuple[CastMember, ...] = room.desk()
        self.vocabulary = room.vocabulary()

    def _match_brief(self, plan: Plan, bible: ShowBible) -> SegmentBrief:
        pairing = plan.fixture()
        match = self.matches.prepare(pairing.home_id, pairing.away_id)
        if plan.kind is SegmentKind.PREVIEW:
            return preview_brief(self.room, bible, plan, match.setup)
        seed = match_seed(self.room.world.world_seed, plan.season, pairing.index)
        return recap_brief(self.room, bible, plan, match.setup, match.play(seed))

    def _brief(self, plan: Plan, bible: ShowBible) -> SegmentBrief:
        if plan.kind in {SegmentKind.PREVIEW, SegmentKind.RECAP}:
            return self._match_brief(plan, bible)
        builders = {
            SegmentKind.CLUB_HISTORY: lambda: club_history_brief(self.room, bible, plan.subject),
            SegmentKind.MANAGER_STORY: lambda: manager_story_brief(self.room, bible, plan.subject),
            SegmentKind.PLAYER_STORY: lambda: player_story_brief(self.room, bible, plan.subject),
            SegmentKind.TABLE_TALK: lambda: table_brief(self.room, bible),
            SegmentKind.BANTER: lambda: banter_brief(self.room, bible),
        }
        return builders[plan.kind]()

    def _material(self, plan: Plan, bible: ShowBible) -> Material:
        if plan.kind is not SegmentKind.INTERVIEW:
            return Material(self._brief(plan, bible), self.cast)
        brief = interview_brief(self.room, bible, plan)
        guest = guest_member(self.room, plan.subject)
        if brief is None or guest is None:
            msg = f"segment {plan.number}: no guest {plan.subject!r} in this world"
            raise ProductionError(msg, plan)
        return Material(brief, (*self.cast, guest), guest)

    def _rules(self, material: Material, prompt: Prompt, bible: ShowBible) -> ReplyRules:
        brief, speakers = material.brief, material.speakers
        remembered = [text_of(m) for m in bible.memories if m.id in prompt.memory_ids]
        context = " ".join(
            [*remembered, *bible.last_lines, json.dumps(brief.facts, ensure_ascii=False)]
        )
        hosts = {member.id: member.id for member in speakers} | {m.name: m.id for m in speakers}
        allowed = set(brief.names) | {member.name for member in speakers}
        allowed |= {member.birthplace for member in speakers if member.birthplace}
        allowed |= names_in(" ".join([*remembered, *bible.last_lines]), self.vocabulary)
        return ReplyRules(
            hosts=hosts,
            memory_ids=prompt.memory_ids,
            allowed_names=frozenset(allowed),
            vocabulary=self.vocabulary,
            allowed_numbers=frozenset(numbers_in(context)),
            min_lines=MIN_LINES,
            max_lines=MAX_LINES,
            ask_predictions=brief.ask_predictions,
            recent=frozenset(words(line.partition(": ")[2]) for line in bible.last_lines),
            must_speak=frozenset({material.guest.id}) if material.guest else frozenset(),
        )

    def _ask(self, prompt: Prompt, rules: ReplyRules, plan: Plan) -> tuple[Reply, int]:
        feedback = ""
        last = ReplyError("no attempt was made")
        for attempt in range(1, ATTEMPTS + 1):
            raw = self.chat.complete(prompt.system, prompt.user + feedback)
            try:
                return parse_reply(raw, rules), attempt
            except ReplyError as error:
                feedback = (
                    f"\n\nYour previous reply was rejected: {error}. "
                    "Reply again with corrected JSON only."
                )
                last = error
        msg = f"segment {plan.number} ({plan.kind.value}) failed {ATTEMPTS} times: {last}"
        raise ProductionError(msg, plan)

    def _talk(
        self, plan: Plan, bible: ShowBible, material: Material
    ) -> tuple[Segment, ShowBible, int]:
        """Ask the model, check the reply and book everything the segment leaves behind."""
        prompt = build_prompt(material.brief, material.speakers, bible)
        reply, attempts = self._ask(prompt, self._rules(material, prompt, bible), plan)
        segment = build_segment(plan, material.brief, material.speakers, reply)
        aired = Aired(plan, material.brief, reply, segment, self.cast, self.roster, material.guest)
        return segment, aired_segment(bible, aired), attempts

    def _desk(self, segment: Segment, bible: ShowBible) -> Segment:
        """The segment carrying the ticker and memories as they stand once it has aired."""
        return with_aftermath(segment, aftermath(self.room, self.roster, bible, self.cast))

    def _break(self, plan: Plan, bible: ShowBible) -> Production:
        segment = break_segment(self.room, self.roster, bible, plan)
        after = advance(bible, plan, self.roster)
        return Production(self._desk(segment, after), after, 0)

    def produce(self, bible: ShowBible) -> Production:
        """Make the next segment. Raises ``ChatError`` if the model is unreachable.

        A segment someone asked for (a guest) is slotted in later, so it carries no ticker or
        memories of its own: the viewer keeps showing those of the segment before it.
        """
        plan = next_plan(bible, self.roster)
        if plan.kind is SegmentKind.BREAK:
            return self._break(plan, bible)
        segment, after, attempts = self._talk(plan, bible, self._material(plan, bible))
        return Production(
            segment if plan.off_rundown else self._desk(segment, after), after, attempts
        )

    def breaking(self, bible: ShowBible, headline: str) -> Breaking:
        """BREAKING NEWS: the flash goes out at once, then the hosts react if the model answers."""
        number = bible.segment_count + 1
        ticker = (f"BREAKING: {headline}",)
        stinger = stinger_segment(number, headline).model_copy(update={"ticker": ticker})
        counted = bible.model_copy(update={"segment_count": number})
        plan = Plan(number + 1, SegmentKind.BREAKING, bible.season, off_rundown=True)
        material = Material(breaking_brief(self.room, headline), self.cast)
        try:
            segment, after, _ = self._talk(plan, counted, material)
        except (ChatError, ProductionError) as error:
            return Breaking((stinger,), counted, f"the hosts have nothing to say yet: {error}")
        return Breaking((stinger, segment.model_copy(update={"ticker": ticker})), after)

    def request_guest(self, bible: ShowBible, who: str) -> tuple[ShowBible, str]:
        """Queue a guest for the next interview. Returns the bible and the guest's name, or ''."""
        person_id = resolve_guest(self.room, who)
        member = guest_member(self.room, person_id) if person_id else None
        if person_id is None or member is None:
            return bible, ""
        requests = (*bible.requests, GuestRequest(person_id=person_id))
        return bible.model_copy(update={"requests": requests}), member.name

    def failed(self, bible: ShowBible, error: ProductionError) -> ShowBible:
        """The bible after a failed attempt: after three in a row the show skips that segment."""
        failures = bible.failures + 1
        if failures < MAX_FAILURES:
            return bible.model_copy(update={"failures": failures})
        return advance(bible, error.plan, self.roster)
