"""Draw an injury for a player hurt in a match: type, length and return date (pure, seeded)."""

from __future__ import annotations

import datetime as dt

from footystreams.domain.injury import Injury, InjurySeverity
from footystreams.domain.rng import WorldRng
from footystreams.domain.static_tables import InjuryCatalog, InjuryType
from footystreams.league.config import RecoveryConfig

MIN_DURATION_FACTOR = 0.5  # medical facilities never more than halve a lay-off


def draw_injury_type(catalog: InjuryCatalog, config: RecoveryConfig, rng: WorldRng) -> InjuryType:
    """Severity by the configured weights, then a type of that severity by its own weight."""
    weights = {
        InjurySeverity(name): weight
        for name, weight in sorted(config.injury_severity_weights.items())
    }
    severity = rng.choice_weighted(weights)
    options = {option.id: option.weight for option in catalog.of_severity(severity)}
    return catalog.injuries[rng.choice_weighted(options)]


def duration_days(
    injury: InjuryType, medical_level: int, config: RecoveryConfig, rng: WorldRng
) -> int:
    """Days out: uniform in the type's range, shortened by the club's medical level."""
    base = rng.randint(injury.min_days, injury.max_days)
    factor = max(MIN_DURATION_FACTOR, 1.0 - config.injury_day_per_medical_level * medical_level)
    return max(1, round(base * factor))


def draw_injury(
    today: dt.date,
    context: tuple[InjuryCatalog, RecoveryConfig, int],
    rng: WorldRng,
) -> Injury:
    """The injury a player suffers today; ``context`` is (catalog, config, medical level)."""
    catalog, config, medical_level = context
    kind = draw_injury_type(catalog, config, rng.fork("kind"))
    days = duration_days(kind, medical_level, config, rng.fork("days"))
    return Injury(
        type=kind.id,
        body_part=kind.body_part,
        severity=kind.severity,
        started_on=today,
        expected_return_on=today + dt.timedelta(days=days),
    )
