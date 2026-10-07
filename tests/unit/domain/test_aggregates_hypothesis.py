"""Hypothesis round-trips and range rejection for Manager, Club, Competition."""

from __future__ import annotations

import pytest
from hypothesis import given
from pydantic import ValidationError

from footystreams.domain.club import Club
from footystreams.domain.competition import Competition, Season
from footystreams.domain.manager import Manager, Philosophy
from tests.factories.strategies import clubs, competitions, managers, seasons


@given(managers())
def test_manager__round_trip_json(manager: Manager) -> None:
    assert Manager.model_validate_json(manager.model_dump_json()) == manager


@given(clubs())
def test_club__round_trip_json(club: Club) -> None:
    assert Club.model_validate_json(club.model_dump_json()) == club


@given(competitions())
def test_competition__round_trip_json(competition: Competition) -> None:
    assert Competition.model_validate_json(competition.model_dump_json()) == competition


@given(seasons())
def test_season__round_trip_json(season: Season) -> None:
    assert Season.model_validate_json(season.model_dump_json()) == season


def test_philosophy__unit_out_of_range__rejected() -> None:
    with pytest.raises(ValidationError):
        Philosophy(
            possession_preference=1.5,
            directness=0.5,
            pressing_intensity=0.5,
            tempo=0.5,
            width=0.5,
            defensive_line=0.5,
            risk_taking=0.5,
        )


@given(clubs())
def test_club__short_code_must_be_three_uppercase(club: Club) -> None:
    payload = club.model_dump()
    payload["short_code"] = "ab"
    with pytest.raises(ValidationError):
        Club.model_validate(payload)


@given(managers())
def test_manager__attribute_out_of_range__rejected(manager: Manager) -> None:
    payload = manager.model_dump()
    payload["attributes"]["tactical_knowledge"] = 0
    with pytest.raises(ValidationError):
        Manager.model_validate(payload)
