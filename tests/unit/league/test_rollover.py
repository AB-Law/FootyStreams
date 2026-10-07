"""The off-season: one four-club season followed by its rollover."""

from __future__ import annotations

import datetime as dt
from collections import Counter

import pytest

from footystreams.domain.player import Player, PlayerStatus
from footystreams.domain.transfer import OUTSIDE_WORLD
from footystreams.league.squad import is_keeper
from tests.factories.league_config import make_development_config
from tests.factories.league_run import cached_rolled_over, play_seasons, season_fingerprint

pytestmark = pytest.mark.timeout(120)  # these build whole seasons; allow for a loaded machine

SQUAD = make_development_config().squad


def _players() -> list[Player]:
    _, factory = cached_rolled_over()
    with factory() as uow:
        return uow.players.all()


def test_rollover__creates_the_next_season_with_next_years_dates() -> None:
    _, factory = cached_rolled_over()
    with factory() as uow:
        old, new = sorted(uow.seasons.all(), key=lambda s: s.starts_on)
    assert new.label == "2032/33"
    assert new.competition_id == old.competition_id
    assert new.starts_on == dt.date(2032, 8, 15)
    assert new.matchdays == old.matchdays
    assert new.id != old.id


def test_rollover__every_player_is_valid_and_within_potential() -> None:
    for player in _players():
        assert type(player).model_validate(player.model_dump(mode="json")) == player
        assert player.ability_current <= player.ability_potential


def test_rollover__retired_players_have_no_club_and_no_club_player_is_retired() -> None:
    players = _players()
    retired = [p for p in players if p.status is PlayerStatus.RETIRED]
    assert retired
    assert all(p.contract is None for p in retired)
    assert all(p.contract is None for p in players if p.status is PlayerStatus.FREE_AGENT)


def test_rollover__every_club_keeps_a_legal_senior_squad_with_keepers() -> None:
    _, factory = cached_rolled_over()
    with factory() as uow:
        clubs = uow.clubs.all()
    players = _players()
    for club in clubs:
        seniors = [
            p
            for p in players
            if p.contract
            and p.contract.club_id == club.id
            and not p.is_youth
            and p.status is PlayerStatus.ACTIVE
        ]
        assert SQUAD.min_senior <= len(seniors) <= SQUAD.max_senior
        assert sum(is_keeper(p) for p in seniors) >= SQUAD.min_goalkeepers


def test_rollover__squad_entries_match_the_players_under_contract() -> None:
    _, factory = cached_rolled_over()
    with factory() as uow:
        entries = uow.squad_entries.all()
    contracted = {
        (p.contract.club_id, p.id)
        for p in _players()
        if p.contract is not None
        and p.status is PlayerStatus.ACTIVE
        and p.contract.club_id != OUTSIDE_WORLD
    }
    assert {(e.club_id, e.player_id) for e in entries} == contracted
    for club_id in {e.club_id for e in entries}:
        numbers = [e.squad_number for e in entries if e.club_id == club_id]
        assert len(numbers) == len(set(numbers))


def test_rollover__nobody_is_left_on_an_expired_contract() -> None:
    boundary = dt.date(2032, 6, 2)
    for player in _players():
        if player.contract is not None:
            assert player.contract.end > boundary


def test_rollover__names_stay_unique() -> None:
    names = Counter(p.known_as for p in _players())
    assert max(names.values()) == 1


def test_rollover__publishes_the_awards_and_retirements_to_the_feed() -> None:
    _, factory = cached_rolled_over()
    with factory() as uow:
        kinds = {e.kind for e in uow.world_events.all()}
    assert {"league_champion", "retirement"} <= kinds


def test_rollover__clubs_get_new_budgets_and_sponsors_that_run_past_today() -> None:
    _, factory = cached_rolled_over()
    with factory() as uow:
        clubs = [c for c in uow.clubs.all() if c.id != OUTSIDE_WORLD]
    for club in clubs:
        assert club.finances.wage_budget_weekly > 0
        assert all(d.ends_on > dt.date(2032, 6, 1) for d in club.finances.sponsor_deals)


def test_rollover__same_seed_twice__identical_world_after_two_seasons() -> None:
    _, first = play_seasons(2)
    _, second = play_seasons(2)
    assert season_fingerprint(first) == season_fingerprint(second)


def test_rollover__the_journal_never_exceeds_its_bound() -> None:
    assert all(len(p.development_log) <= 24 for p in _players())
