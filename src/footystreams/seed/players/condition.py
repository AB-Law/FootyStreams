"""Starting condition of a generated player: fitness, form and the occasional minor injury."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from footystreams.domain.injury import Injury, InjurySeverity
from footystreams.domain.rng import WorldRng
from footystreams.domain.static_tables import InjuryCatalog

FITNESS_RANGE = (0.80, 0.97)
FATIGUE_RANGE = (0.0, 0.10)
SHARPNESS_RANGE = (0.60, 0.90)
MORALE_RANGE = (0.45, 0.65)
FORM_MEAN = 0.5
FORM_DEVIATION = 0.05
INJURED_AT_START_CHANCE = 0.03
STARTING_INJURY_SEVERITIES = (InjurySeverity.KNOCK, InjurySeverity.MINOR)


@dataclass(frozen=True, slots=True)
class StartingCondition:
    """Condition fields copied onto the Player."""

    fitness: float
    fatigue: float
    match_sharpness: float
    morale: float
    form: float
    injury: Injury | None


def _starting_injury(rng: WorldRng, catalog: InjuryCatalog, today: dt.date) -> Injury:
    severity = rng.choice(STARTING_INJURY_SEVERITIES)
    kind = rng.choice_weighted({item: item.weight for item in catalog.of_severity(severity)})
    length = rng.randint(max(1, kind.min_days), max(1, kind.max_days))
    elapsed = rng.randint(0, length - 1)
    started = today - dt.timedelta(days=elapsed)
    return Injury(
        type=kind.id,
        body_part=kind.body_part,
        severity=kind.severity,
        started_on=started,
        expected_return_on=started + dt.timedelta(days=length),
    )


def starting_condition(rng: WorldRng, catalog: InjuryCatalog, today: dt.date) -> StartingCondition:
    """Fit, fresh and in decent spirits; two to four percent start with a minor knock."""
    injured = rng.bernoulli(INJURED_AT_START_CHANCE)
    return StartingCondition(
        fitness=rng.uniform(*FITNESS_RANGE),
        fatigue=rng.uniform(*FATIGUE_RANGE),
        match_sharpness=rng.uniform(*SHARPNESS_RANGE),
        morale=rng.uniform(*MORALE_RANGE),
        form=rng.truncated_normal(FORM_MEAN, FORM_DEVIATION, 0.0, 1.0),
        injury=_starting_injury(rng, catalog, today) if injured else None,
    )
