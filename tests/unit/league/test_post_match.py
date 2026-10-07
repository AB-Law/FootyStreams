from __future__ import annotations

import datetime as dt

import pytest

from footystreams.domain.injury import Suspension
from footystreams.domain.player import CareerStint
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import PlayerId
from footystreams.events.discipline import InjuryEvent
from footystreams.events.summary import PlayerMatchStats
from footystreams.league.condition import PlayedMatch, apply_match, serve_suspension
from footystreams.league.delta import WorldDelta
from footystreams.league.injuries import draw_injury
from footystreams.league.outcome import Outcome
from footystreams.league.post_match import PlayedFixture, derive_world_delta
from tests.factories.league_config import make_league_config
from tests.factories.league_inputs import make_played_fixture, make_post_match_tables
from tests.factories.world import cached_static_tables

RECOVERY = make_league_config().recovery
TABLES = make_post_match_tables()
TODAY = dt.date(2031, 8, 15)


def _delta(played: PlayedFixture) -> WorldDelta:
    return derive_world_delta(played, TABLES, WorldRng(3))


def _stats(**changes: object) -> PlayerMatchStats:
    base = PlayerMatchStats(player_id=PlayerId("plr_00001"), minutes=90, rating=7.0)
    return base.model_copy(update=changes)


def test_derive_world_delta__records_match_fixture_summary_and_log() -> None:
    played = make_played_fixture()
    delta = _delta(played)
    (match,) = delta.matches
    assert (match.home_goals, match.away_goals) == (
        played.result.summary.score_home,
        played.result.summary.score_away,
    )
    assert match.id == played.setup.match_id
    assert delta.fixtures[0].match_id == match.id
    assert [e.seq for e in delta.events] == [e.seq for e in played.result.events]
    assert delta.summaries[0].summary == played.result.summary


def test_derive_world_delta__same_inputs__same_delta() -> None:
    played = make_played_fixture()
    assert _delta(played).content_hash() == _delta(played).content_hash()


def test_derive_world_delta__players_who_played__are_tired_and_sharper_by_their_minutes() -> None:
    played = make_played_fixture()
    before = {p.id: p for team in played.teams for p in team.squad}
    delta = _delta(played)
    minutes = {str(s.player_id): s.minutes for s in played.result.summary.player_stats}
    for player in delta.players:
        if player.id not in minutes:
            continue
        expected = min(
            1.0, before[player.id].fatigue + minutes[player.id] * RECOVERY.fatigue_per_match_minute
        )
        assert player.fatigue == pytest.approx(expected, abs=1e-4)
        assert player.match_sharpness >= before[player.id].match_sharpness


def test_derive_world_delta__career_goals_and_apps__match_the_summary() -> None:
    played = make_played_fixture()
    before = {p.id: p for team in played.teams for p in team.squad}
    delta = _delta(played)
    updated = {p.id: p for p in delta.players}
    summary = played.result.summary
    for row in summary.player_stats:
        old = sum(s.apps for s in before[row.player_id].career_history)
        new = sum(s.apps for s in updated[row.player_id].career_history)
        assert new - old == 1
    goals_before = sum(s.goals for p in before.values() for s in p.career_history)
    goals_after = sum(s.goals for p in updated.values() for s in p.career_history) + sum(
        s.goals for pid, p in before.items() if pid not in updated for s in p.career_history
    )
    assert goals_after - goals_before == summary.score_home + summary.score_away


def test_derive_world_delta__home_club__books_gate_and_the_balance_follows_the_ledger() -> None:
    played = make_played_fixture()
    delta = _delta(played)
    home_id = played.teams[0].club.id
    assert any(e.club_id == home_id and e.memo_key == "gate" for e in delta.ledger)
    for club in delta.clubs:
        moved = sum(e.amount for e in delta.ledger if e.club_id == club.id)
        original = next(t.club for t in played.teams if t.club.id == club.id)
        assert club.finances.balance == original.finances.balance + moved


def _with_injury() -> PlayedFixture:
    for seed in range(120):
        played = make_played_fixture(sim_seed=seed)
        if any(isinstance(event, InjuryEvent) for event in played.result.events):
            return played
    pytest.fail("no injury in 120 matches")


def test_derive_world_delta__an_injury_event__records_an_injury_with_a_return_date() -> None:
    played = _with_injury()
    hurt = {e.player_id for e in played.result.events if isinstance(e, InjuryEvent)}
    delta = _delta(played)
    injured = [p for p in delta.players if p.id in hurt]
    assert injured
    for player in injured:
        assert player.current_injury is not None
        assert player.current_injury.expected_return_on > played.today


def test_derive_world_delta__every_player_row__is_a_valid_player() -> None:
    delta = _delta(make_played_fixture())
    for player in delta.players:
        assert type(player).model_validate(player.model_dump(mode="json")) == player


def test_apply_match__red_card__bans_for_the_configured_matches() -> None:
    played = make_played_fixture()
    player = played.teams[0].squad[0]
    after = apply_match(player, PlayedMatch(_stats(reds=1), Outcome.LOSS, None), (RECOVERY, TODAY))
    assert after.suspension == Suspension(
        matches_remaining=RECOVERY.red_card_ban_matches, reason="red card"
    )
    assert after.discipline.reds_season == 1


def test_apply_match__fifth_yellow__bans_one_match() -> None:
    player = make_played_fixture().teams[0].squad[0]
    four = player.model_copy(
        update={"discipline": player.discipline.model_copy(update={"yellows_season": 4})}
    )
    after = apply_match(four, PlayedMatch(_stats(yellows=1), Outcome.DRAW, None), (RECOVERY, TODAY))
    assert after.suspension is not None
    assert after.suspension.matches_remaining == 1
    assert after.discipline.yellow_ban_threshold_progress == 0


def test_apply_match__win_lifts_morale_and_loss_lowers_it() -> None:
    player = make_played_fixture().teams[0].squad[0]
    win = apply_match(player, PlayedMatch(_stats(), Outcome.WIN, None), (RECOVERY, TODAY))
    loss = apply_match(player, PlayedMatch(_stats(), Outcome.LOSS, None), (RECOVERY, TODAY))
    assert loss.morale < player.morale < win.morale or player.morale in {0.0, 1.0}


def test_apply_match__a_great_rating__pulls_form_up() -> None:
    player = make_played_fixture().teams[0].squad[0].model_copy(update={"form": 0.4})
    after = apply_match(
        player, PlayedMatch(_stats(rating=9.5), Outcome.WIN, None), (RECOVERY, TODAY)
    )
    assert after.form > 0.4
    assert len(after.form_history) == len(player.form_history) + 1


def test_serve_suspension__counts_down_and_clears() -> None:
    player = make_played_fixture().teams[0].squad[0]
    banned = player.model_copy(update={"suspension": Suspension(matches_remaining=2, reason="x")})
    once = serve_suspension(banned)
    assert once.suspension is not None
    assert once.suspension.matches_remaining == 1
    assert serve_suspension(once).suspension is None
    assert serve_suspension(player) is player


def test_draw_injury__better_medical_level__shortens_the_layoff_on_average() -> None:
    catalog = cached_static_tables().injuries

    def mean_days(level: int) -> float:
        injuries = [draw_injury(TODAY, (catalog, RECOVERY, level), WorldRng(s)) for s in range(200)]
        return sum((i.expected_return_on - i.started_on).days for i in injuries) / 200

    assert mean_days(90) < mean_days(0)


def test_draw_injury__every_draw__stays_inside_its_types_range() -> None:
    catalog = cached_static_tables().injuries
    for seed in range(100):
        injury = draw_injury(TODAY, (catalog, RECOVERY, 0), WorldRng(seed))
        kind = catalog.injuries[injury.type]
        days = (injury.expected_return_on - injury.started_on).days
        assert max(1, kind.min_days) <= days <= kind.max_days
        assert injury.severity is kind.severity


def test_apply_match__open_career_spell__is_extended_in_place() -> None:
    player = make_played_fixture().teams[0].squad[0]
    open_spell = CareerStint(club_id=player.contract.club_id, from_date=TODAY, apps=4, goals=1)  # type: ignore[union-attr]
    with_spell = player.model_copy(update={"career_history": (*player.career_history, open_spell)})
    after = apply_match(
        with_spell, PlayedMatch(_stats(goals=2), Outcome.WIN, None), (RECOVERY, TODAY)
    )
    last = after.career_history[-1]
    assert (last.apps, last.goals) == (5, 3)
    assert len(after.career_history) == len(with_spell.career_history)
