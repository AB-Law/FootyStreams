"""``verify_world``: the world-level invariant catalogue (design 10 section 9, plus seed checks).

Codes: W01 foreign keys, W02 squads, W03 money, W07 one squad per player, W08 contracts and shirts,
W09 CA <= PA, W10 cached ability; C01-C08 are the seed coherence checks of design 05 section 5
(names, nationality mix, referees, crew, managers, prospects, league shape). The schedule check
(05 section 5, item 9) arrives with the schedule in M9.
"""

from __future__ import annotations

from footystreams.domain.world import World
from footystreams.verify.violation import Violation
from footystreams.verify.world_money import check_money
from footystreams.verify.world_people import (
    check_abilities,
    check_crew,
    check_managers,
    check_names,
    check_nationality_mix,
    check_prospect_flags,
    check_referees,
)
from footystreams.verify.world_refs import check_references, check_registration
from footystreams.verify.world_shape import check_league_shape
from footystreams.verify.world_squads import check_squads
from footystreams.verify.world_targets import WorldChecks, WorldTargets


def verify_world(world: World, checks: WorldChecks, targets: WorldTargets) -> list[Violation]:
    """Run every world check and return all violations (empty means the world is coherent)."""
    return [
        *check_references(world),
        *check_registration(world),
        *check_squads(world, checks, targets),
        *check_money(world, targets),
        *check_abilities(world, checks),
        *check_names(world, checks, targets),
        *check_nationality_mix(world, targets),
        *check_referees(world, targets),
        *check_crew(world, targets),
        *check_managers(world, checks),
        *check_prospect_flags(world),
        *check_league_shape(world, checks, targets),
    ]
