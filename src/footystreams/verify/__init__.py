"""The single invariant catalogue for matches, worlds and seasons.

May import: domain, events. Used by tests, strict mode, soak runs and the production pre-air gate.
Design: docs/design/10-testing-strategy.md section 9.
"""

from footystreams.verify.league import (
from footystreams.verify.league import check_ledger, check_results, check_season_complete
from footystreams.verify.match import verify_match
from footystreams.verify.violation import Violation, format_violations
from footystreams.verify.world import verify_world
from footystreams.verify.world_targets import WorldChecks, WorldTargets

__all__ = [
    "SquadRules",
    "Violation",
    "WorldChecks",
    "WorldTargets",
    "check_development",
    "check_ledger",
    "check_results",
    "check_season_complete",
    "check_squads",
    "format_violations",
    "verify_match",
    "verify_world",
]
