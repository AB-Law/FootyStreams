"""Tests for Person, Personality and Appearance."""

from __future__ import annotations

import datetime as dt

import pytest
from hypothesis import given
from pydantic import ValidationError

from footystreams.domain.person import Appearance, Person, Personality
from tests.factories.person import make_person
from tests.factories.strategies import appearances, personalities, persons


def test_appearance__skin_tone_out_of_range__rejected() -> None:
    with pytest.raises(ValidationError):
        Appearance(
            skin_tone=0,
            hair_style="short",
            hair_colour="black",
            facial_hair="none",
            build="athletic",
        )


def test_person__age_on__before_birthday__subtracts_year() -> None:
    person = make_person(date_of_birth=dt.date(2000, 6, 15))
    assert person.age_on(dt.date(2020, 6, 14)) == 19
    assert person.age_on(dt.date(2020, 6, 15)) == 20


def test_make_person__validates() -> None:
    assert make_person().known_as == "Brae"


@given(persons())
def test_person__round_trip_json(person: Person) -> None:
    restored = Person.model_validate_json(person.model_dump_json())
    assert restored == person


@given(personalities())
def test_personality__round_trip(personality: Personality) -> None:
    assert Personality.model_validate_json(personality.model_dump_json()) == personality


@given(appearances())
def test_appearance__round_trip(appearance: Appearance) -> None:
    assert Appearance.model_validate_json(appearance.model_dump_json()) == appearance
