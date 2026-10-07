"""Inputs of the world checks: the tables they read and the thresholds they enforce."""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.roles import RoleCatalog
from footystreams.domain.static_tables import FormationCatalog


@dataclass(frozen=True, slots=True)
class WorldTargets:
    """Thresholds of docs/design/05-seeding.md section 5, supplied by the caller from data."""

    min_team_gap: float
    max_team_gap: float
    min_adjacent_gap: float
    min_senior_squad: int = 22
    max_senior_squad: int = 28
    min_goalkeepers: int = 2
    bench_size: int = 9
    xi_size: int = 11
    coverage_competence: int = 70
    coverage_depth: int = 2
    min_wage_ratio: float = 0.85
    max_wage_ratio: float = 1.25
    overspend_ratio: float = 1.05
    max_overspenders: int = 2
    min_nationalities: int = 4
    max_nation_share: float = 0.55
    max_surname_repeats: int = 2
    min_crew_distance: float = 20.0
    home_bias_mean_band: tuple[float, float] = (0.0, 0.25)
    strict_referee: float = 0.75
    lenient_referee: float = 0.25
    card_happy_referee: float = 0.85


@dataclass(frozen=True, slots=True)
class WorldChecks:
    """Static tables and the real-world name denylist (plain lower-case letters)."""

    roles: RoleCatalog
    formations: FormationCatalog
    denylist: frozenset[str]
