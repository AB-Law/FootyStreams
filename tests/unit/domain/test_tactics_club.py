"""Tests for TeamTactics and Club aggregate."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from footystreams.domain.club import (
    Board,
    Club,
    ClubColours,
    ClubLocation,
    Facilities,
    Fanbase,
    KitSpec,
    YouthAcademy,
)
from footystreams.domain.finance import ClubFinances
from footystreams.domain.stadium import Pitch, Stadium
from footystreams.domain.tactics import TeamTactics, module_or_default
from footystreams.domain.tactics.modules.v1 import ModuleKey
from footystreams.domain.types import ClubId, NationId
from tests.factories.tactics import make_team_tactics


def test_team_tactics__requires_eleven_slots() -> None:
    tactics = make_team_tactics()
    payload = tactics.model_dump()
    payload["slots"] = payload["slots"][:10]
    with pytest.raises(ValidationError):
        TeamTactics.model_validate(payload)


def test_module_or_default__returns_build_up() -> None:
    tactics = make_team_tactics()
    module = module_or_default(tactics, ModuleKey.BUILD_UP)
    assert module.kind == "build_up"


def test_club__round_trip() -> None:
    tactics = make_team_tactics()
    club = Club(
        id=ClubId("clb_home01"),
        name="Harbour FC",
        short_name="Harbour",
        short_code="HAR",
        colours=ClubColours(
            primary="#111111",
            secondary="#eeeeee",
            accent="#ff0000",
            home_kit=KitSpec(),
            away_kit=KitSpec(),
        ),
        founded_year=1920,
        location=ClubLocation(city="Harbour", nation_id=NationId("nat_kesh01"), population=200_000),
        stadium=Stadium(
            name="Harbour Park",
            capacity=25_000,
            pitch=Pitch(length_m=105, width_m=68, quality=0.7),
            atmosphere=0.6,
            proximity=0.5,
        ),
        fanbase=Fanbase(
            size=40_000,
            passion=0.6,
            toxicity=0.3,
            fickleness=0.4,
            away_following=0.3,
        ),
        finances=ClubFinances(
            balance=5_000_000,
            wage_budget_weekly=200_000,
            transfer_budget=1_000_000,
            last_reconciled_on=dt.date(2026, 1, 1),
        ),
        facilities=Facilities(training=60, youth=55, medical=50),
        academy=YouthAcademy(level=50, intake_size=4, intake_quality=0.5),
        board=Board(ambition=55, patience=50, meddling=40, budget_strictness=50),
        club_reputation=60,
        default_tactics=tactics,
    )
    assert Club.model_validate_json(club.model_dump_json()) == club
    assert TeamTactics.model_validate_json(tactics.model_dump_json()) == tactics
