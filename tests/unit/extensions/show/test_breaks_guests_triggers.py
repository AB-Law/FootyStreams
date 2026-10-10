"""Breaks, guests and breaking news: the pieces that are not a plain talking segment."""

from __future__ import annotations

import json

import pytest

from footystreams.extensions.show.bible import ShowBible
from footystreams.extensions.show.breaking import clean_headline
from footystreams.extensions.show.breaks import ADS, break_segment, stinger_segment
from footystreams.extensions.show.facts_interview import guest_member, guest_ref, interview_brief
from footystreams.extensions.show.models import SegmentKind
from footystreams.extensions.show.plan import Plan
from footystreams.extensions.show.producer import ChatModel, Producer, Production, ProductionError
from footystreams.extensions.show.triggers import parse_trigger, resolve_guest
from tests.factories.show import (
    EchoChat,
    FakeMatches,
    ScriptedChat,
    chat_error,
    fresh_bible,
    newsroom,
)


def maker(chat: ChatModel | None = None) -> Producer:
    return Producer(newsroom(), chat or EchoChat(), FakeMatches())


def air(producer: Producer, bible: ShowBible, count: int) -> list[Production]:
    made = []
    for _ in range(count):
        step = producer.produce(bible)
        bible = step.bible
        made.append(step)
    return made


def talk(speakers: list[str], word: str = "point") -> list[dict[str, str]]:
    """Eight distinct lines shared out among ``speakers``."""
    return [
        {
            "speaker_id": speakers[i % len(speakers)],
            "text": f"Another fine line about topic {w} here.",
        }
        for i, w in enumerate(
            ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", word]
        )
    ]


def test_break__is_a_slideshow_with_no_talk() -> None:
    plan = Plan(6, SegmentKind.BREAK, 1)
    segment = break_segment(newsroom(), maker().roster, fresh_bible(), plan)
    assert segment.kind is SegmentKind.BREAK
    assert segment.lines == ()
    assert [slide.kind for slide in segment.slides] == ["ad", "ad", "fixture"]
    assert segment.duration_s == sum(slide.seconds for slide in segment.slides)


def test_break__shows_the_table_or_the_results_once_there_are_some() -> None:
    producer = maker()
    bible = air(producer, fresh_bible(), 3)[-1].bible
    kinds: set[str] = set()
    for number in (6, 7):
        plan = Plan(number, SegmentKind.BREAK, 1)
        kinds |= {s.kind for s in break_segment(newsroom(), producer.roster, bible, plan).slides}
    assert {"table", "results"} <= kinds


def test_break__rotates_through_the_sponsors() -> None:
    producer = maker()
    brands = {
        slide.title
        for number in range(1, 12)
        for slide in break_segment(
            newsroom(), producer.roster, fresh_bible(), Plan(number, SegmentKind.BREAK, 1)
        ).slides
        if slide.kind == "ad"
    }
    assert len(brands) == len(ADS)


def test_stinger__flashes_the_headline_and_marks_the_segment_as_breaking() -> None:
    flash = stinger_segment(12, "Seisund County sack their manager")
    assert flash.alert == "Seisund County sack their manager"
    assert flash.slides[0].kind == "breaking"
    assert flash.slides[0].lines == ("Seisund County sack their manager",)


def test_clean_headline__is_plain_one_line_and_short() -> None:
    assert clean_headline("**Big** news\n“now” \N{GRINNING FACE}") == 'Big news "now"'
    assert len(clean_headline("x" * 500)) == 120


@pytest.mark.parametrize(
    "bad",
    [
        "nope",
        "[]",
        '{"kind": "party", "text": "x"}',
        '{"kind": "guest", "text": ""}',
        json.dumps({"kind": "guest", "text": "x" * 500}),
    ],
)
def test_parse_trigger__refuses_what_is_not_a_trigger(bad: str) -> None:
    with pytest.raises(ValueError, match="not a trigger"):
        parse_trigger(bad)


def test_parse_trigger__reads_a_good_one() -> None:
    trigger = parse_trigger('{"kind": "breaking", "text": "Big news"}')
    assert (trigger.kind, trigger.text) == ("breaking", "Big news")


def test_resolve_guest__by_id_name_or_start_of_a_name() -> None:
    room = newsroom()
    manager = sorted(room.managers.values(), key=lambda m: str(m.id))[0]
    assert resolve_guest(room, str(manager.id)) == str(manager.id)
    assert resolve_guest(room, manager.known_as) == str(manager.id)
    assert resolve_guest(room, manager.known_as.upper()[:4]) is not None
    assert resolve_guest(room, "Nobody Atall Exists") is None
    assert resolve_guest(room, "  ") is None


def test_resolve_guest__finds_players_too() -> None:
    room = newsroom()
    player = sorted(room.players.values(), key=lambda p: str(p.id))[0]
    assert resolve_guest(room, player.known_as) is not None


def test_guest_ref__a_player_wears_their_club_colours_and_their_own_face() -> None:
    room = newsroom()
    player_id = next(pid for pid in sorted(room.players) if pid in room.club_of_player)
    guest = guest_ref(room, fresh_bible(), player_id)
    assert guest is not None
    club = room.clubs[room.club_of_player[player_id]]
    assert guest.kind == "player"
    assert guest.kit_primary == club.colours.primary
    assert guest.kit_secondary == club.colours.secondary
    assert guest.appearance["hair_style"] == room.players[player_id].appearance.hair_style
    assert guest.role == f"{club.short_name} player"


def test_guest_ref__a_manager_is_introduced_by_club() -> None:
    room = newsroom()
    club = next(c for c in room.clubs.values() if c.manager_id)
    guest = guest_ref(room, fresh_bible(), str(club.manager_id))
    assert guest is not None
    assert guest.kind == "manager"
    assert guest.role == f"{club.short_name} manager"


def test_guest_ref__nobody_is_nobody() -> None:
    assert guest_ref(newsroom(), fresh_bible(), "plr_zzzzzzz") is None
    assert guest_member(newsroom(), "plr_zzzzzzz") is None


def test_interview_brief__gives_the_model_the_career_and_character_of_the_guest() -> None:
    room = newsroom()
    club = next(c for c in room.clubs.values() if c.manager_id)
    plan = Plan(4, SegmentKind.INTERVIEW, 1, subject=str(club.manager_id), off_rundown=True)
    brief = interview_brief(room, fresh_bible(), plan)
    assert brief is not None
    json.dumps(brief.facts)
    assert brief.facts["personality"]
    assert brief.guest is not None
    assert club.name in brief.names
    assert brief.teaser.startswith("Interview: ")
    unknown = Plan(4, SegmentKind.INTERVIEW, 1, subject="mgr_zzzzzzz")
    assert interview_brief(room, fresh_bible(), unknown) is None


def test_produce__the_rundown_gives_a_post_match_interview_then_a_break() -> None:
    steps = air(maker(), fresh_bible(), 6)
    kinds = [step.segment.kind for step in steps]
    assert kinds[2] is SegmentKind.RECAP
    assert kinds[3] is SegmentKind.INTERVIEW
    assert kinds[5] is SegmentKind.BREAK
    interview = steps[3].segment
    assert interview.guest is not None
    assert interview.teaser == "Post-match interview"
    assert interview.guest.id in {line.speaker_id for line in interview.lines}
    assert steps[5].segment.slides
    assert steps[5].segment.ticker


def test_produce__the_guest_is_remembered_by_the_hosts() -> None:
    steps = air(maker(), fresh_bible(), 4)
    remembered = [m for m in steps[-1].bible.memories if m.kind == "interview"]
    guest = steps[3].segment.guest
    assert guest is not None
    assert len(remembered) == 1
    assert guest.id in remembered[0].related_ids


def test_produce__a_guest_cannot_leave_memories_of_their_own() -> None:
    steps = air(maker(), fresh_bible(), 4)
    guest = steps[3].segment.guest
    assert guest is not None
    assert all(str(m.owner.id) != guest.id for m in steps[-1].bible.memories)


def test_produce__a_requested_guest_comes_next_and_leaves_the_rundown_alone() -> None:
    producer = maker()
    bible, name = producer.request_guest(fresh_bible(), "Jorsen")
    assert name
    step = producer.produce(bible)
    assert step.segment.kind is SegmentKind.INTERVIEW
    assert step.segment.guest is not None
    assert step.segment.guest.name == name
    assert step.segment.ticker == ()
    assert step.segment.teaser.startswith("Interview: ")
    assert step.bible.requests == ()
    assert step.bible.step == bible.step
    assert producer.produce(step.bible).segment.kind is SegmentKind.PREVIEW


def test_request_guest__somebody_who_does_not_exist_is_not_booked() -> None:
    bible, name = maker().request_guest(fresh_bible(), "Nobody Atall Exists")
    assert name == ""
    assert bible.requests == ()


def test_produce__an_interview_in_which_the_guest_never_speaks_is_sent_back() -> None:
    producer = maker()
    bible, _ = producer.request_guest(fresh_bible(), "Jorsen")
    hosts = [member.id for member in producer.cast]
    chat = ScriptedChat(*[json.dumps({"lines": talk(hosts)})] * 3)
    with pytest.raises(ProductionError, match="must speak"):
        Producer(newsroom(), chat, FakeMatches()).produce(bible)


def test_breaking__the_flash_goes_first_then_the_hosts_react() -> None:
    bible = fresh_bible()
    made = maker().breaking(bible, "Seisund County sack their manager")
    flash, reaction = made.segments
    assert flash.slides[0].kind == "breaking"
    assert reaction.kind is SegmentKind.BREAKING
    assert reaction.alert == "Seisund County sack their manager"
    assert reaction.ticker == ("BREAKING: Seisund County sack their manager",)
    assert made.bible.segment_count == bible.segment_count + 2
    assert made.bible.step == bible.step
    assert any(m.kind == "breaking" for m in made.bible.memories)


def test_breaking__if_the_model_is_away_only_the_flash_airs() -> None:
    made = maker(ScriptedChat(chat_error("connection refused"))).breaking(
        fresh_bible(), "Something has happened"
    )
    assert [s.kind for s in made.segments] == [SegmentKind.BREAK]
    assert "nothing to say" in made.note
    assert made.bible.segment_count == 1


def test_breaking__the_hosts_may_not_add_numbers_the_headline_does_not_give() -> None:
    producer = maker()
    hosts = [member.id for member in producer.cast]
    lines = [
        {
            "speaker_id": hosts[i % 3],
            "text": f"They paid 42 million for this, apparently, line {w}.",
        }
        for i, w in enumerate("abcdefgh")
    ]
    chat = ScriptedChat(*[json.dumps({"lines": lines})] * 3)
    made = Producer(newsroom(), chat, FakeMatches()).breaking(
        fresh_bible(), "A transfer has been agreed"
    )
    assert [s.kind for s in made.segments] == [SegmentKind.BREAK]
