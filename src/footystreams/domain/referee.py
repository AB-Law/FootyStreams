"""Match official (Referee)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar, Self

from pydantic import Field, model_validator

from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.person import Person
from footystreams.domain.types import Disposition, Id, Signed, Unit

HOME_BIAS_MIN = -0.2
HOME_BIAS_MAX = 0.5


class PersonRef(DomainModel):
    """Lightweight person pointer for assistants/video officials."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {"id": "R", "known_as": "R"}

    id: Id
    known_as: str = Field(min_length=1, max_length=40)


class Referee(Person):
    """Match referee with decision-tendency sliders."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        **Person.__usage__,
        "strictness": "S",
        "consistency": "S",
        "home_bias": "S",
        "card_tendency": "S",
        "advantage_tendency": "S",
        "added_time_generosity": "S",
        "penalty_propensity": "S",
        "video_reliance": "S",
        "fitness": "S",
        "temperament": "R",
        "assistants": "R",
        "video_official": "R",
    }

    strictness: Unit
    consistency: Unit
    home_bias: Signed
    card_tendency: Unit
    advantage_tendency: Unit
    added_time_generosity: Unit
    penalty_propensity: Unit
    video_reliance: Unit
    fitness: Unit
    temperament: Disposition = 50
    assistants: tuple[PersonRef, ...] = ()
    video_official: PersonRef | None = None

    @model_validator(mode="after")
    def _home_bias_band(self) -> Self:
        if not HOME_BIAS_MIN <= self.home_bias <= HOME_BIAS_MAX:
            msg = f"home_bias typical band is [{HOME_BIAS_MIN}, {HOME_BIAS_MAX}]"
            raise ValueError(msg)
        return self
