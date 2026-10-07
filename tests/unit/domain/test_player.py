"""Tests for Player core and attribute groups."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from footystreams.domain.attributes import TechnicalAttrs
from footystreams.domain.player import Player
from footystreams.domain.types import Position
from tests.factories.player import make_player, make_technical


def test_make_player__validates() -> None:
    player = make_player()
    assert player.primary_position is Position.ST
    assert player.ability_potential >= player.ability_current


def test_player__pa_below_ca__rejected() -> None:
    with pytest.raises(ValidationError):
        make_player(ability_current=80, ability_potential=70)


def test_player__bmi_too_high__rejected() -> None:
    with pytest.raises(ValidationError):
        make_player(height_cm=155, weight_kg=105)


def test_player__gk_with_high_outfield__rejected() -> None:
    with pytest.raises(ValidationError):
        make_player(
            position_competence={Position.GK: 90, Position.ST: 50},
            primary_position=Position.GK,
        )


def test_player__outfield_high_gk__rejected() -> None:
    with pytest.raises(ValidationError):
        make_player(
            position_competence={Position.ST: 90, Position.GK: 50},
            primary_position=Position.ST,
        )


def test_player__non_youth_without_natural_position__rejected() -> None:
    with pytest.raises(ValidationError):
        make_player(
            position_competence={Position.ST: 70, Position.GK: 10},
            primary_position=Position.ST,
            is_youth=False,
        )


@given(st.builds(make_technical, finishing=st.integers(1, 100)))
def test_technical__round_trip(attrs: TechnicalAttrs) -> None:
    assert TechnicalAttrs.model_validate_json(attrs.model_dump_json()) == attrs


@given(st.sampled_from([None, 1, 9, 99]))
def test_player__round_trip_json(squad_number: int | None) -> None:
    player = make_player(squad_number=squad_number)
    restored = Player.model_validate_json(player.model_dump_json())
    assert restored == player
