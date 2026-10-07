from __future__ import annotations

import datetime as dt

from footystreams.domain.player import Player, PlayerStatus, SquadStatus
from footystreams.domain.types import ClubId
from footystreams.domain.world import SquadEntry
from footystreams.league.squad import (
    SquadContext,
    SquadMoves,
    assign_numbers,
    is_keeper,
    rebalance,
    released,
    signed_free_agent,
    squad_entries,
)
from tests.factories.league_config import make_development_config
from tests.factories.world import make_world

WORLD = make_world(1)
CONFIG = make_development_config()
TODAY = dt.date(2032, 6, 1)
CONTEXT = SquadContext(TODAY, CONFIG.squad, CONFIG.youth)
CLUB = WORLD.clubs[0].id
SQUAD = [p for p in WORLD.players if p.contract and p.contract.club_id == CLUB]
SENIORS = [p for p in SQUAD if not p.is_youth]
YOUTHS = [p for p in SQUAD if p.is_youth]
POOL = [p for p in WORLD.players if p.status is PlayerStatus.FREE_AGENT]


def _senior_total(players: list[Player], moves: SquadMoves) -> int:
    gone = {p.id for p in moves.released}
    kept = [p for p in players if not p.is_youth and p.id not in gone]
    return len(kept) + len(moves.promoted) + len(moves.signed)


def test_rebalance__a_full_squad__changes_nothing_but_merit_promotions() -> None:
    moves = rebalance(CLUB, SQUAD, POOL, CONTEXT)
    assert moves.signed == []
    assert moves.released == []
    assert all(p.is_youth is False for p in moves.promoted)


def test_rebalance__short_squad__is_filled_to_the_minimum_from_youth_then_the_pool() -> None:
    short = [*SENIORS[:18], *YOUTHS]
    moves = rebalance(CLUB, short, POOL, CONTEXT)
    assert _senior_total(short, moves) >= CONFIG.squad.min_senior
    assert all(s.contract and s.contract.club_id == CLUB for s in moves.signed)
    assert all(p.status is PlayerStatus.ACTIVE for p in moves.signed)


def test_rebalance__keeper_shortage__brings_in_a_keeper() -> None:
    keepers = [p for p in SENIORS if is_keeper(p)]
    without = [p for p in SENIORS if not is_keeper(p)] + keepers[:1]
    moves = rebalance(CLUB, without, POOL, CONTEXT)
    arrivals = [*moves.promoted, *moves.signed]
    assert any(is_keeper(p) for p in arrivals)


def test_rebalance__surplus__releases_the_weakest_and_keeps_two_keepers() -> None:
    extras = [p.model_copy(update={"id": f"plr_x{i:04d}"}) for i, p in enumerate(POOL[:8])]
    bloated = [*SENIORS, *(e.model_copy(update={"is_youth": False}) for e in extras)]
    moves = rebalance(CLUB, bloated, [], CONTEXT)
    assert _senior_total(bloated, moves) <= CONFIG.squad.max_senior
    assert moves.released
    gone = {p.id for p in moves.released}
    assert sum(is_keeper(p) for p in bloated if p.id not in gone) >= CONFIG.squad.min_goalkeepers
    weakest_kept = min(p.ability_current for p in bloated if p.id not in gone)
    assert all(r.ability_current <= weakest_kept + 40 for r in moves.released)
    assert all(r.contract is None and r.status is PlayerStatus.FREE_AGENT for r in moves.released)


def test_rebalance__no_one_available__stops_without_looping_forever() -> None:
    moves = rebalance(CLUB, SENIORS[:5], [], CONTEXT)
    assert moves.signed == []


def test_rebalance__a_strong_adult_prospect__is_promoted_on_merit() -> None:
    star = YOUTHS[0].model_copy(update={"ability_current": 90, "ability_potential": 95})
    old_enough = star.model_copy(update={"date_of_birth": dt.date(2013, 1, 1)})
    short_squad = [*SENIORS[:24], old_enough]
    moves = rebalance(CLUB, short_squad, [], CONTEXT)
    assert [p.id for p in moves.promoted] == [old_enough.id]


def test_signed_free_agent__gets_a_short_contract_at_the_going_wage() -> None:
    agent = POOL[0]
    signed = signed_free_agent(agent, CLUB, TODAY, 1)
    assert signed.contract is not None
    assert signed.contract.end == dt.date(2033, 6, 30)
    assert signed.contract.wage_weekly > 0


def test_released__clears_club_ties() -> None:
    gone = released(SENIORS[0])
    assert gone.contract is None
    assert gone.squad_number is None
    assert gone.squad_status is SquadStatus.FREE_AGENT


def test_assign_numbers__gives_every_player_a_distinct_number() -> None:
    bare = [p.model_copy(update={"squad_number": None}) for p in SQUAD]
    numbered = assign_numbers(bare)
    numbers = [p.squad_number for p in numbered]
    assert len(set(numbers)) == len(numbers)
    assert all(n is not None and n >= 12 for n in numbers)
    assert all(p.squad_number >= 32 for p in numbered if p.is_youth)  # type: ignore[operator]


def test_assign_numbers__keeps_existing_numbers() -> None:
    kept = assign_numbers(SQUAD)
    assert [p.squad_number for p in kept] == [p.squad_number for p in SQUAD]


def test_squad_entries__wants_one_per_player_and_deletes_stale_ones() -> None:
    stale = SquadEntry(
        club_id=ClubId(CLUB), player_id="plr_gone1", squad_number=99,  # type: ignore[arg-type]
        status=SquadStatus.FIRST_TEAM, squad_role=SENIORS[0].contract.squad_role,  # type: ignore[union-attr]
    )  # fmt: skip
    wanted, deleted = squad_entries(CLUB, SQUAD, [stale])
    assert len(wanted) == len(SQUAD)
    assert deleted == [f"{CLUB}:plr_gone1"]
    assert {e.player_id for e in wanted} == {p.id for p in SQUAD}
