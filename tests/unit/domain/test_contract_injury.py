"""Tests for contract, injury and player condition fields."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from footystreams.domain.contract import Contract, SquadRole
from footystreams.domain.injury import Injury, InjurySeverity
from footystreams.domain.types import ClubId
from tests.factories.player import make_player


def test_injury__return_before_start__rejected() -> None:
    with pytest.raises(ValidationError):
        Injury(
            type="hamstring",
            body_part="left_thigh",
            severity=InjurySeverity.MINOR,
            started_on=dt.date(2026, 3, 10),
            expected_return_on=dt.date(2026, 3, 1),
        )


def test_player__with_contract_and_injury__validates() -> None:
    club = ClubId("clb_home01")
    player = make_player(
        contract=Contract(
            club_id=club,
            start=dt.date(2024, 7, 1),
            end=dt.date(2027, 6, 30),
            wage_weekly=25_000,
            squad_role=SquadRole.KEY,
        ),
        current_injury=Injury(
            type="knock",
            body_part="ankle",
            severity=InjurySeverity.KNOCK,
            started_on=dt.date(2026, 1, 1),
            expected_return_on=dt.date(2026, 1, 8),
        ),
        fatigue=0.2,
        form=0.6,
    )
    assert player.contract is not None
    assert player.current_injury is not None
    restored = player.__class__.model_validate_json(player.model_dump_json())
    assert restored == player
