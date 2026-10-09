"""Making segments end to end with a scripted model and the seed world: briefs, checks, memory."""

from __future__ import annotations

import json

import pytest

from footystreams.extensions.show.bible import ShowBible
from footystreams.extensions.show.facts import (
    banter_brief,
    club_history_brief,
    manager_story_brief,
    player_story_brief,
    table_brief,
)
from footystreams.extensions.show.models import SegmentKind
from footystreams.extensions.show.producer import ChatError, ChatModel, Producer, ProductionError
from footystreams.extensions.show.prompt import available_catchphrases
from tests.factories.show import (
    EchoChat,
    FakeMatches,
    ScriptedChat,
    chat_error,
    fresh_bible,
    newsroom,
)


def producer(chat: ChatModel | None = None) -> Producer:
    return Producer(newsroom(), chat or EchoChat(), FakeMatches())


def air(maker: Producer, bible: ShowBible, count: int) -> ShowBible:
    for _ in range(count):
        bible = maker.produce(bible).bible
    return bible


# ---------------------------------------------------------------------------- the briefs


def test_briefs__every_kind_is_json_ready_and_names_who_may_be_spoken_of() -> None:
    room, bible = newsroom(), fresh_bible()
    club = sorted(room.clubs)[0]
    manager = next(iter(sorted(room.managers)))
    player = next(pid for pid, p in sorted(room.players.items()) if p.career_history)
    briefs = [
        club_history_brief(room, bible, club),
        manager_story_brief(room, bible, manager),
        player_story_brief(room, bible, player),
        table_brief(room, bible),
        banter_brief(room, bible),
    ]
    for brief in briefs:
        json.dumps(brief.facts)
        assert brief.goal
        assert brief.title
    assert room.clubs[club].name in briefs[0].names
    assert room.clubs[club].stadium.name in briefs[0].names
    assert briefs[0].screen is not None
    assert briefs[3].screen is not None
    assert briefs[3].screen.kind == "table"


def test_briefs__a_club_history_carries_its_rivalry_and_founding() -> None:
    room = newsroom()
    club = next(c for c in room.clubs.values() if c.rivalries)
    brief = club_history_brief(room, fresh_bible(), str(club.id))
    assert brief.facts["founded_year"] == club.founded_year
    derby = brief.facts["derby"]
    assert isinstance(derby, dict)
    assert derby["label"] == club.rivalries[0].label


# ---------------------------------------------------------------------------- producing


def test_produce__a_preview_records_each_hosts_pick_and_moves_the_rundown_on() -> None:
    maker = producer()
    made = maker.produce(fresh_bible())
    assert made.segment.kind is SegmentKind.PREVIEW
    assert len(made.bible.predictions) == 3
    assert {p.host_id for p in made.bible.predictions} == {member.id for member in maker.cast}
    assert made.bible.segment_count == 1
    assert made.bible.step == 1
    assert made.segment.screen is not None
    assert made.segment.duration_s > sum(line.duration_ms for line in made.segment.lines) / 1000


def test_produce__a_recap_books_the_result_settles_picks_and_remembers_the_match() -> None:
    maker = producer()
    bible = air(maker, fresh_bible(), 2)
    made = maker.produce(bible)
    assert made.segment.kind is SegmentKind.RECAP
    after = made.bible
    assert len(after.results) == 1
    assert after.predictions == ()
    kinds = {m.kind for m in after.memories}
    assert {"match_moment", "prediction_result"} <= kinds
    assert after.date == after.results[0].date
    assert made.segment.screen is not None
    assert made.segment.screen.kind == "score"
    assert after.fixture_index == 1


def test_produce__new_memories_from_the_model_are_kept_as_the_models() -> None:
    maker = producer()
    after = maker.produce(fresh_bible()).bible
    joke = next(m for m in after.memories if m.kind == "running_joke")
    assert joke.facts["origin"] == "llm"
    assert "car park" in str(joke.facts["text"])


def test_produce__the_same_joke_told_again_is_recalled_not_duplicated() -> None:
    maker = producer()
    bible = air(maker, fresh_bible(), 3)
    jokes = [m for m in bible.memories if m.kind == "running_joke"]
    assert len(jokes) == 1
    assert int(jokes[0].facts["recalled"]) >= 2


def test_produce__memories_come_back_into_the_next_prompt() -> None:
    chat = EchoChat()
    maker = producer(chat)
    air(maker, fresh_bible(), 2)
    prompt = json.loads(chat.calls[-1][1])
    remembered = [m["text"] for host in prompt["hosts"] for m in host["memories"]]
    assert any("car park" in text for text in remembered)


def test_produce__a_used_catchphrase_is_held_back_for_a_while() -> None:
    maker = producer()
    host = maker.cast[1]
    phrase = host.catchphrases[0]
    speakers = [member.id for member in maker.cast]
    lines = [{"speaker_id": host.id, "text": f"{phrase} That is all I have to say about it."}]
    lines += [
        {
            "speaker_id": speakers[index % 3],
            "text": f"Here is another fine line about topic {word}.",
        }
        for index, word in enumerate(
            ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf")
        )
    ]
    picks = [{"host_id": speaker, "pick": "draw"} for speaker in speakers]
    chat = ScriptedChat(json.dumps({"lines": lines, "predictions": picks}))
    made = Producer(newsroom(), chat, FakeMatches()).produce(fresh_bible())
    assert made.bible.catchphrase_uses[f"{host.id}|{phrase}"] == 1
    held_back = available_catchphrases(host, made.bible)
    assert phrase not in held_back
    assert set(held_back) == set(host.catchphrases) - {phrase}


def test_produce__a_bad_reply_is_retried_with_the_reason() -> None:
    good = EchoChat()
    bad = json.dumps({"lines": [{"speaker_id": "med_00001", "text": "short"}]})

    class Flaky:
        def __init__(self) -> None:
            self.sent: list[str] = []

        def complete(self, system: str, user: str) -> str:
            self.sent.append(user)
            return (
                bad
                if len(self.sent) == 1
                else good.complete(system, user.split("\n\nYour previous", maxsplit=1)[0])
            )

    flaky = Flaky()
    made = Producer(newsroom(), flaky, FakeMatches()).produce(fresh_bible())
    assert made.attempts == 2
    assert "Your previous reply was rejected" in flaky.sent[1]


def test_produce__gives_up_after_three_bad_replies_and_skips_after_three_failed_plans() -> None:
    maker = Producer(newsroom(), ScriptedChat(*["not json"] * 9), FakeMatches())
    bible = fresh_bible()
    for expected in (1, 2):
        with pytest.raises(ProductionError) as raised:
            maker.produce(bible)
        bible = maker.failed(bible, raised.value)
        assert bible.failures == expected
        assert bible.segment_count == 0
    with pytest.raises(ProductionError) as raised:
        maker.produce(bible)
    skipped = maker.failed(bible, raised.value)
    assert skipped.failures == 0
    assert skipped.segment_count == 1
    assert skipped.step == 1


def test_produce__an_unreachable_model_is_not_a_failed_segment() -> None:
    maker = Producer(newsroom(), ScriptedChat(chat_error("connection refused")), FakeMatches())
    with pytest.raises(ChatError):
        maker.produce(fresh_bible())


def test_produce__the_bible_survives_a_round_trip_through_json() -> None:
    maker = producer()
    bible = air(maker, fresh_bible(), 3)
    assert ShowBible.model_validate_json(bible.model_dump_json()) == bible
