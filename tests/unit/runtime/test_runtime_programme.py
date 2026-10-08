from __future__ import annotations

import pytest

from footystreams.domain.fixture import FixtureStatus
from footystreams.runtime.config import Programme
from footystreams.runtime.cursor import Cursor, Phase
from footystreams.runtime.programme import (
    Block,
    BlockKind,
    after,
    build_programme,
    filler_id,
    news_of,
)
from tests.factories.league_run import cached_small_season, make_runner

PROGRAMME = Programme()
ONE_MATCHDAY = [
    BlockKind.PRE_MATCH,
    BlockKind.MATCH,
    BlockKind.POST_MATCH,
    BlockKind.PRE_MATCH,
    BlockKind.MATCH,
    BlockKind.POST_MATCH,
    BlockKind.MATCHDAY_MAGAZINE,
]


def _blocks(quarantined: tuple[str, ...] = ()) -> list[Block]:
    _, factory = cached_small_season()
    with factory() as uow:
        return build_programme(uow, PROGRAMME, quarantined)


def test_programme__a_four_club_season_is_six_matchdays_of_two_matches_and_a_magazine() -> None:
    blocks = _blocks()

    assert len(blocks) == 6 * len(ONE_MATCHDAY)
    assert [b.kind for b in blocks] == ONE_MATCHDAY * 6


def test_programme__ids_are_unique_and_already_in_broadcast_order() -> None:
    ids = [block.id for block in _blocks()]

    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)


def test_programme__a_match_block_lasts_the_playing_time_plus_the_half_time_break() -> None:
    _, factory = cached_small_season()
    blocks = _blocks()
    first = next(b for b in blocks if b.kind is BlockKind.MATCH)

    with factory() as uow:
        played = uow.summaries.require(first.subject_ref).summary.duration_s

    assert first.duration_s == played + PROGRAMME.half_time_s
    assert first.subject_ref.startswith("mch_")


def test_programme__segments_carry_the_facts_a_presenter_needs() -> None:
    blocks = _blocks()
    pre = blocks[0]
    post = blocks[2]
    magazine = blocks[6]

    assert {"home", "away", "home_code", "away_code", "derby", "matchday"} <= set(pre.facts)
    assert {"home_goals", "away_goals"} <= set(post.facts)
    assert magazine.facts["matches"] == 2
    assert magazine.facts["matchday"] == 1


def test_programme__durations_come_from_the_programme_settings() -> None:
    _, factory = cached_small_season()
    with factory() as uow:
        blocks = build_programme(uow, Programme(pre_match_s=7.0, magazine_s=9.0))

    assert blocks[0].duration_s == 7.0
    assert blocks[6].duration_s == 9.0


def test_programme__a_quarantined_match_airs_as_filler_in_its_place() -> None:
    blocks = _blocks()
    victim = blocks[1].subject_ref

    withheld = _blocks((victim,))

    assert len(withheld) == len(blocks) - 2
    swapped = [b for b in withheld if b.facts.get("reason") == "quarantined"]
    assert [b.kind for b in swapped] == [BlockKind.FILLER]
    assert swapped[0].facts["match_id"] == victim
    assert all(b.subject_ref != victim for b in withheld)
    assert [b.id for b in withheld] == sorted(b.id for b in withheld)


def test_programme__a_matchday_with_a_match_still_to_play_has_no_magazine_yet() -> None:
    runner, factory = make_runner(2, 4)
    with factory() as uow:
        season = uow.seasons.all()[0]
    runner.prepare(season)
    while not runner.run_day().matches_played:
        pass
    with factory() as uow:  # as after a crash between the two matches of the matchday
        unplayed = sorted(uow.fixtures.find({"status": "played"}), key=lambda f: f.id)[1]
        uow.fixtures.save(unplayed.model_copy(update={"status": FixtureStatus.SCHEDULED}))
        uow.commit()

    with factory() as uow:
        blocks = build_programme(uow, PROGRAMME)

    assert [b.kind for b in blocks] == [BlockKind.PRE_MATCH, BlockKind.MATCH, BlockKind.POST_MATCH]


def test_after__no_cursor_means_everything_and_a_done_block_is_not_repeated() -> None:
    blocks = _blocks()

    assert after(blocks, None) == blocks
    assert after(blocks, Cursor(blocks[3].id, Phase.DONE)) == blocks[4:]


def test_after__a_block_in_progress_is_resumed_not_skipped() -> None:
    blocks = _blocks()

    assert after(blocks, Cursor(blocks[4].id, Phase.STARTED, 120)) == blocks[4:]


def test_after__a_cursor_past_the_end_leaves_nothing() -> None:
    blocks = _blocks()

    assert after(blocks, Cursor(blocks[-1].id, Phase.DONE)) == []


def test_filler_ids__are_numbered_and_never_collide_with_programme_ids() -> None:
    assert filler_id(3) == "filler:000003"
    assert all(not block.id.startswith("filler:") for block in _blocks())


def test_news_of__lists_only_public_events_of_that_day_in_id_order() -> None:
    _, factory = cached_small_season()
    with factory() as uow:
        dates = {event.date for event in uow.world_events.all()}
        date = next(iter(sorted(dates)))
        news = news_of(uow, date)

    assert news
    assert all(event.date == date for event in news)
    assert [e.id for e in news] == sorted(e.id for e in news)


@pytest.mark.parametrize("ordinal", [0, 1, 2])
def test_block_ids__a_matchs_blocks_sort_pre_match_then_match_then_post(ordinal: int) -> None:
    blocks = _blocks()

    assert blocks[ordinal].id.endswith(f":{ordinal}")
