"""Memory strength and retrieval, and the rundown that decides what airs next."""

from __future__ import annotations

import datetime as dt
from typing import Any

from footystreams.domain.memory import MemoryRecord
from footystreams.extensions.show.bible import GuestRequest, Result, new_bible
from footystreams.extensions.show.memory import (
    MemorySpec,
    make_memory,
    mark_recalled,
    memory_id,
    prune,
    recalls,
    retrieve,
    slug,
    strength,
    text_of,
)
from footystreams.extensions.show.models import SegmentKind
from footystreams.extensions.show.plan import Plan, Roster, advance, kind_for, next_plan
from footystreams.extensions.show.schedule import season_fixtures

TODAY = dt.date(2031, 7, 1)
HOST = "med_00001"
OTHER = "med_00002"


def memory(
    number: int, kind: str = "running_joke", text: str = "the car park again", **extra: Any
) -> MemoryRecord:
    return make_memory(number, TODAY, MemorySpec(host_id=HOST, kind=kind, text=text, **extra))


def test_strength__fades_with_time() -> None:
    joke = memory(1)
    assert strength(joke, TODAY) > strength(joke, TODAY + dt.timedelta(days=200))


def test_strength__fades_slower_when_it_keeps_coming_up() -> None:
    fresh = memory(1)
    often = fresh
    for _ in range(4):
        often = mark_recalled(often, TODAY)
    later = TODAY + dt.timedelta(days=150)
    assert strength(often, later) > strength(fresh, later)
    assert recalls(often) == 4


def test_strength__never_falls_to_nothing() -> None:
    joke = memory(1)
    assert strength(joke, TODAY + dt.timedelta(days=100_000)) > 0


def test_strength__important_memories_outlast_trivial_ones() -> None:
    big, small = memory(1, salience=0.9), memory(2, salience=0.2)
    later = TODAY + dt.timedelta(days=90)
    assert strength(big, later) > strength(small, later)


def test_retrieve__only_what_the_host_holds_or_shares() -> None:
    mine = memory(1)
    shared = make_memory(
        2, TODAY, MemorySpec(host_id=OTHER, kind="opinion", text="a shared view", related=[HOST])
    )
    theirs = make_memory(3, TODAY, MemorySpec(host_id=OTHER, kind="opinion", text="a private view"))
    found = retrieve([mine, shared, theirs], HOST, frozenset(), TODAY, 5)
    assert {m.id for m in found} == {mine.id, shared.id}


def test_retrieve__prefers_what_is_on_topic() -> None:
    on_topic = memory(1, text="about the derby", related=["clb_00001"], salience=0.4)
    off_topic = memory(2, text="about the weather", salience=0.5)
    found = retrieve([off_topic, on_topic], HOST, frozenset({"clb_00001"}), TODAY, 2)
    assert found[0].id == on_topic.id


def test_retrieve__respects_the_limit() -> None:
    many = [memory(n, text=f"memory number {n} words") for n in range(1, 8)]
    assert len(retrieve(many, HOST, frozenset(), TODAY, 3)) == 3


def test_make_memory__keeps_its_text_and_a_stable_key() -> None:
    joke = memory(5, text="The car park again, every single week.")
    assert text_of(joke) == "The car park again, every single week."
    assert joke.id == memory_id(5)
    assert joke.summary_key.startswith("running_joke:the-car-park-again")
    assert joke.owner.id == HOST


def test_slug__ignores_accents_and_punctuation() -> None:
    assert slug("Gathiški!! Albion, again?") == "gathiski-albion-again"


def test_prune__keeps_the_strongest_and_the_order() -> None:
    items = [memory(n, text=f"memory {n}", salience=0.1 * n) for n in range(1, 6)]
    kept = prune(items, TODAY, cap=3)
    assert [m.id for m in kept] == [items[2].id, items[3].id, items[4].id]
    assert prune(items, TODAY, cap=10) == tuple(items)


# ---------------------------------------------------------------------------- the rundown

ROSTER = Roster(
    fixtures=season_fixtures([f"clb_{n:05d}" for n in range(1, 9)]),
    clubs=tuple(f"clb_{n:05d}" for n in range(1, 9)),
    managers=("mgr_00001", "mgr_00002"),
    players=("plr_00001", "plr_00002", "plr_00003"),
    manager_of={"clb_00001": "mgr_00001", "clb_00002": "mgr_00002"},
)
CYCLE = 6


def run(steps: int) -> list[Plan]:
    bible = new_bible(TODAY)
    plans = []
    for _ in range(steps):
        plan = next_plan(bible, ROSTER)
        plans.append(plan)
        bible = advance(bible, plan, ROSTER)
    return plans


def test_rundown__each_fixture_is_preview_filler_recap_interview_filler_break() -> None:
    kinds = [plan.kind for plan in run(2 * CYCLE)]
    assert kinds[:CYCLE][0] is SegmentKind.PREVIEW
    assert kinds[2] is SegmentKind.RECAP
    assert kinds[3] is SegmentKind.INTERVIEW
    assert kinds[5] is SegmentKind.BREAK
    assert kinds[CYCLE] is SegmentKind.PREVIEW
    assert kinds[CYCLE + 2] is SegmentKind.RECAP
    assert SegmentKind.PREVIEW not in (kinds[1], kinds[4])


def test_rundown__preview_and_recap_are_about_the_same_fixture() -> None:
    plans = run(2 * CYCLE)
    assert plans[0].pairing == plans[2].pairing
    assert plans[CYCLE].pairing == plans[CYCLE + 2].pairing
    assert plans[0].pairing != plans[CYCLE].pairing


def test_rundown__the_table_follows_each_matchday() -> None:
    plans = run(CYCLE * 4)
    after_matchday = [plans[index].kind for index in range(4, CYCLE * 4, CYCLE)]
    assert SegmentKind.TABLE_TALK not in after_matchday[:3]
    assert after_matchday[3] is SegmentKind.TABLE_TALK


def test_rundown__a_season_rolls_into_the_next() -> None:
    bible = new_bible(TODAY)
    for _ in range(len(ROSTER.fixtures) * CYCLE):
        bible = advance(bible, next_plan(bible, ROSTER), ROSTER)
    assert bible.season == 2
    assert bible.fixture_index == 0
    assert kind_for(bible) is SegmentKind.PREVIEW


def test_rundown__fillers_take_whoever_has_been_off_air_longest() -> None:
    clubs = [plan.subject for plan in run(CYCLE * 30) if plan.kind is SegmentKind.CLUB_HISTORY]
    assert len(clubs) >= 8
    assert len(set(clubs[:8])) == 8


def test_rundown__a_restart_picks_up_where_the_bible_says() -> None:
    bible = new_bible(TODAY)
    for _ in range(5):
        bible = advance(bible, next_plan(bible, ROSTER), ROSTER)
    again = new_bible(TODAY).model_validate_json(bible.model_dump_json())
    assert next_plan(again, ROSTER) == next_plan(bible, ROSTER)


def test_rundown__the_post_match_guest_alternates_between_the_player_and_a_manager() -> None:
    result = Result(
        fixture_key="s1-f000",
        season=1,
        matchday=1,
        date="2031-07-01",
        home_id="clb_00001",
        away_id="clb_00002",
        home_name="A",
        away_name="B",
        home_goals=2,
        away_goals=0,
        potm_id="plr_00002",
    )
    first = new_bible(TODAY).model_copy(
        update={"results": (result,), "step": 3, "fixture_index": 1}
    )
    second = first.model_copy(update={"fixture_index": 2})
    assert next_plan(first, ROSTER).subject == "plr_00002"
    assert next_plan(second, ROSTER).subject == "mgr_00001"


def test_rundown__a_requested_guest_takes_the_next_slot_without_moving_the_rundown() -> None:
    bible = new_bible(TODAY).model_copy(update={"requests": (GuestRequest(person_id="plr_00003"),)})
    plan = next_plan(bible, ROSTER)
    assert plan.kind is SegmentKind.INTERVIEW
    assert plan.subject == "plr_00003"
    assert plan.off_rundown
    after = advance(bible, plan, ROSTER)
    assert after.requests == ()
    assert after.step == bible.step
    assert after.segment_count == 1
    assert after.featured["guest:plr_00003"] == 1
    assert next_plan(after, ROSTER).kind is SegmentKind.PREVIEW


def test_rundown__guests_are_queued_in_order() -> None:
    requests = (GuestRequest(person_id="plr_00001"), GuestRequest(person_id="mgr_00002"))
    bible = new_bible(TODAY).model_copy(update={"requests": requests})
    after = advance(bible, next_plan(bible, ROSTER), ROSTER)
    assert next_plan(after, ROSTER).subject == "mgr_00002"
