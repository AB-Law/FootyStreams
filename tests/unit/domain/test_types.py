"""Unit and property tests for domain primitive types."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from footystreams.domain.base import DomainModel
from footystreams.domain.canonical import canonical_json
from footystreams.domain.types import (
    Attribute,
    EntityKind,
    EntityRef,
    Pos,
    Position,
    Signed,
    Unit,
)
from footystreams.domain.versions import SCHEMA_VERSION, SIM_VERSION


class _ScaleHolder(DomainModel):
    """Tiny model so Annotated validators run through Pydantic."""

    attribute: Attribute
    unit: Unit
    signed: Signed


def test_id_pattern__valid_player_id__accepted() -> None:
    ref = EntityRef(kind=EntityKind.PLAYER, id="plr_abc12")
    assert ref.id == "plr_abc12"


def test_id_pattern__invalid__rejected() -> None:
    with pytest.raises(ValidationError):
        EntityRef(kind=EntityKind.PLAYER, id="PLAYER_1")


def test_attribute__out_of_range__rejected() -> None:
    with pytest.raises(ValidationError):
        _ScaleHolder(attribute=0, unit=0.5, signed=0.0)
    with pytest.raises(ValidationError):
        _ScaleHolder(attribute=101, unit=0.5, signed=0.0)


def test_unit__rounds_to_four_decimals() -> None:
    holder = _ScaleHolder(attribute=50, unit=0.123456, signed=-0.123456)
    assert holder.unit == 0.1235
    assert holder.signed == -0.1235


def test_unit__out_of_range__rejected() -> None:
    with pytest.raises(ValidationError):
        _ScaleHolder(attribute=50, unit=1.0001, signed=0.0)
    with pytest.raises(ValidationError):
        _ScaleHolder(attribute=50, unit=0.0, signed=-1.0001)


def test_pos__accepts_corners() -> None:
    assert Pos(x=0.0, y=1.0).model_dump() == {"x": 0.0, "y": 1.0}


def test_position_enum__includes_gk_and_st() -> None:
    assert Position.GK.value == "GK"
    assert Position.ST.value == "ST"


def test_versions__initial_constants() -> None:
    assert SCHEMA_VERSION == "0.1.2"
    assert SIM_VERSION == "0.0.0"


def test_canonical_json__sorts_keys_and_compacts() -> None:
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


@given(
    attr=st.integers(min_value=1, max_value=100),
    unit=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    signed=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_scale_holder__round_trip_json(attr: int, unit: float, signed: float) -> None:
    holder = _ScaleHolder(attribute=attr, unit=unit, signed=signed)
    restored = _ScaleHolder.model_validate_json(holder.model_dump_json())
    assert restored == holder


@given(st.sampled_from(list(EntityKind)), st.from_regex(r"[a-z]{3}_[0-9a-z]{4,12}", fullmatch=True))
def test_entity_ref__round_trip(kind: EntityKind, entity_id: str) -> None:
    ref = EntityRef(kind=kind, id=entity_id)
    assert EntityRef.model_validate_json(ref.model_dump_json()) == ref
