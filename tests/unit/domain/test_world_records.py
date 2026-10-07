from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from pydantic import ValidationError

from footystreams.domain.contract import SquadRole
from footystreams.domain.injury import InjurySeverity
from footystreams.domain.player import SquadStatus
from footystreams.domain.static_tables import (
    Formation,
    FormationSlot,
    InjuryCatalog,
    InjuryType,
    TraitDefinition,
)
from footystreams.domain.types import (
    CityId,
    ClubId,
    FormationId,
    NationId,
    PlayerId,
    Position,
    TraitId,
)
from footystreams.domain.world import City, Nation, SquadEntry, WorldManifest

OUTFIELD_LINE = (
    Position.RB, Position.CB, Position.CB, Position.LB, Position.CM, Position.CM,
    Position.CM, Position.RW, Position.ST, Position.LW,
)  # fmt: skip


def _slots(positions: tuple[Position, ...]) -> tuple[FormationSlot, ...]:
    return tuple(
        FormationSlot(slot=index, position=position, x=0.5, y=0.5)
        for index, position in enumerate(positions)
    )


def _formation(positions: tuple[Position, ...]) -> Formation:
    return Formation(id=FormationId("433"), label="4-3-3", slots=_slots(positions))


def _injury(**overrides: Any) -> InjuryType:
    values: dict[str, Any] = {
        "id": "hamstring_strain",
        "label": "Hamstring strain",
        "body_part": "hamstring",
        "severity": InjurySeverity.MINOR,
        "min_days": 7,
        "max_days": 21,
        "weight": 2.0,
    }
    values.update(overrides)
    return InjuryType(**values)


def test_formation__valid_shape__lists_positions_in_slot_order() -> None:
    formation = _formation((Position.GK, *OUTFIELD_LINE))
    assert formation.positions()[0] is Position.GK
    assert len(formation.positions()) == 11


def test_formation__wrong_slot_count__rejected() -> None:
    with pytest.raises(ValidationError, match=r"slots 0\.\.10"):
        _formation((Position.GK, *OUTFIELD_LINE[:-1]))


def test_formation__keeper_not_first__rejected() -> None:
    with pytest.raises(ValidationError, match="must be the goalkeeper"):
        _formation((Position.CB, Position.GK, *OUTFIELD_LINE[1:]))


def test_formation__two_keepers__rejected() -> None:
    with pytest.raises(ValidationError, match="exactly one goalkeeper"):
        _formation((Position.GK, Position.GK, *OUTFIELD_LINE[1:]))


def test_injury_type__inverted_durations__rejected() -> None:
    with pytest.raises(ValidationError, match="max_days"):
        _injury(min_days=30, max_days=10)


def test_injury_catalog__of_severity__filters_and_sorts_by_id() -> None:
    catalog = InjuryCatalog(
        injuries={
            "b": _injury(id="b"),
            "a": _injury(id="a"),
            "c": _injury(id="c", severity=InjurySeverity.SEVERE),
        }
    )
    assert [item.id for item in catalog.of_severity(InjurySeverity.MINOR)] == ["a", "b"]


def test_trait_definition__non_positive_weight__rejected() -> None:
    with pytest.raises(ValidationError):
        TraitDefinition(id=TraitId("x"), label="X", usage="S", weight=0.0)


def test_world_records__round_trip_through_json() -> None:
    records = [
        Nation(
            id=NationId("nat_valmere"),
            name="Valmere",
            demonym="Valmerian",
            is_home=True,
            name_culture="x",
        ),
        City(
            id=CityId("cty_00001"),
            name="Kesh",
            nation_id=NationId("nat_valmere"),
            population=1000,
            climate="temperate",
        ),
        SquadEntry(
            club_id=ClubId("clb_00001"),
            player_id=PlayerId("plr_00001"),
            squad_number=9,
            status=SquadStatus.FIRST_TEAM,
            squad_role=SquadRole.KEY,
        ),
        WorldManifest(
            world_seed=1,
            generator_version="1",
            schema_version="0.2.0",
            counts={"players": 3},
            content_sha256="0" * 64,
            created_in_world=dt.date(2031, 7, 1),
        ),
    ]
    for record in records:
        assert type(record).model_validate_json(record.model_dump_json()) == record
