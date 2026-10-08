"""The matches a balance run plays: every ordered pairing of a world's clubs, over and over.

Match ``i`` is pairing ``i mod P`` (P = clubs x (clubs - 1)) in replicate ``i div P``. Each
replicate draws its own weather, referee and crowd (the world seed of the setup is derived from the
base seed and the replicate), while the match seed is ``base_seed + i`` as in docs/design/02 s14.5.
Setups are built by the same code as a league match, so the harness measures what a league plays.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from footystreams.domain.match import MatchSetup, TeamSheet
from footystreams.domain.player import Player
from footystreams.domain.ratings import team_rating
from footystreams.domain.rng import derive_seed
from footystreams.domain.transfer import OUTSIDE_WORLD
from footystreams.domain.types import ClubId
from footystreams.league.clock import read_date
from footystreams.league.friendly import build_friendly_setup
from footystreams.league.inputs import load_team
from footystreams.league.matchday import MatchdayEngine
from footystreams.league.simulator import ResultOnlySimulator
from footystreams.league.tables import LeagueTables
from footystreams.persistence.ports import Repositories

SEED_LIMIT = 2**63


@dataclass(frozen=True, slots=True)
class Scenario:
    """One match to play: its setup, its seed and the home side's rating advantage."""

    setup: MatchSetup
    seed: int
    gap: float


def _rating(sheet: TeamSheet, squad: Mapping[str, Player], tables: LeagueTables) -> float:
    starters = [(squad[slot.player_id], slot.role, slot.duty) for slot in sheet.lineup]
    return team_rating(starters, tables.roles)


def _pairings(repositories: Repositories) -> list[tuple[ClubId, ClubId]]:
    clubs = sorted(club.id for club in repositories.clubs.all() if club.id != OUTSIDE_WORLD)
    return [(home, away) for home in clubs for away in clubs if home != away]


def build_scenarios(
    repositories: Repositories,
    tables: LeagueTables,
    matches: int,
    base_seed: int,
    min_gap: float = 0.0,
) -> list[Scenario]:
    """The first ``matches`` scenarios of the endless pairing cycle.

    ``min_gap`` keeps only the pairings whose teams differ in rating by at least that much, so a
    strength study plays mismatches only instead of a world's many near-equal pairs.
    """
    pairings = _pairings(repositories)
    squads = {
        club: {player.id: player for player in load_team(repositories, club).squad}
        for pair in pairings
        for club in pair
    }
    today = read_date(repositories)
    simulator = ResultOnlySimulator(tables.roles, tables.config.result_only)

    def scenario(index: int, pair: tuple[ClubId, ClubId], replicate: int) -> Scenario:
        home, away = pair
        world_seed = derive_seed(base_seed, f"balance:{replicate}")
        engine = MatchdayEngine(tables=tables, simulator=simulator, world_seed=world_seed)
        setup = build_friendly_setup(repositories, home, away, engine, today)
        gap = _rating(setup.home, squads[home], tables) - _rating(setup.away, squads[away], tables)
        return Scenario(setup, (base_seed + index) % SEED_LIMIT, round(gap, 4))

    if min_gap > 0.0:
        pairings = [pair for pair in pairings if abs(scenario(0, pair, 0).gap) >= min_gap]
        if not pairings:
            msg = f"no pairing in this world differs in rating by {min_gap} or more"
            raise ValueError(msg)
    return [
        scenario(index, pairings[index % len(pairings)], index // len(pairings))
        for index in range(matches)
    ]
