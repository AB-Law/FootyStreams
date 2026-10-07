"""Tests for competition, fixtures and standings.compute."""

from __future__ import annotations

import datetime as dt

from footystreams.domain.competition import Competition, MatchRules, Season
from footystreams.domain.standings import MatchScore, compute
from footystreams.domain.types import ClubId, CompetitionId, SeasonId


def test_standings_compute__orders_by_points() -> None:
    season = SeasonId("ssn_2026a")
    a, b = ClubId("clb_aaaa01"), ClubId("clb_bbbb01")
    rows = compute(
        season,
        (a, b),
        (MatchScore(home_club_id=a, away_club_id=b, home_goals=2, away_goals=0),),
    )
    assert rows[0].club_id == a
    assert rows[0].points == 3
    assert rows[1].points == 0


def test_competition_season__round_trip() -> None:
    competition = Competition(
        id=CompetitionId("cmp_league1"),
        name="Premier Division",
        short_name="PD",
        club_ids=(ClubId("clb_aaaa01"), ClubId("clb_bbbb01")),
        rules=MatchRules(),
    )
    season = Season(
        id=SeasonId("ssn_2026a"),
        competition_id=competition.id,
        label="2026",
        starts_on=dt.date(2026, 8, 1),
        ends_on=dt.date(2027, 5, 31),
    )
    assert Competition.model_validate_json(competition.model_dump_json()) == competition
    assert Season.model_validate_json(season.model_dump_json()) == season
