"""Builder for match referees."""

from __future__ import annotations

from typing import Any

from footystreams.domain.referee import Referee
from tests.factories.person import make_person


def make_referee(**overrides: Any) -> Referee:
    """Build a valid, average Referee; override the tendency sliders a test cares about."""
    person = make_person(
        id="ref_test0001", first_name="Will", last_name="Whistle", known_as="Whistle"
    )
    values: dict[str, Any] = {
        **person.model_dump(),
        "strictness": 0.5,
        "consistency": 0.5,
        "home_bias": 0.0,
        "card_tendency": 0.5,
        "advantage_tendency": 0.5,
        "added_time_generosity": 0.5,
        "penalty_propensity": 0.5,
        "video_reliance": 0.5,
        "fitness": 0.8,
    }
    values.update(overrides)
    return Referee(**values)
