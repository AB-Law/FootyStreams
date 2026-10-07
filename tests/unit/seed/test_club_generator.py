from __future__ import annotations

from collections import Counter
from functools import cache

import pytest

from footystreams.domain.contract import SquadRole
from footystreams.domain.rng import WorldRng
from footystreams.domain.squad_strength import squad_strength
from footystreams.domain.types import Position
from footystreams.seed.clubs.generator import ClubDraft, ClubPlan, generate_club
from footystreams.seed.clubs.identity import IdentityRegistry, short_code_for
from footystreams.seed.players.context import GenerationContext
from tests.factories.world import make_generation_context

ARCHETYPES = (
    "giants", "challengers", "old_money", "counter_punchers",
    "academy", "boom_and_bust", "grafters", "minnows",
)  # fmt: skip
TOLERANCE = 0.6 + 0.01


def _draft(ctx: GenerationContext, key: str, seed: int = 1) -> ClubDraft:
    archetype = ctx.tables.clubs.archetypes[key]
    plan = ClubPlan(key, archetype, sum(archetype.quality) / 2)
    cities = list(ctx.geography.cities[ctx.geography.home.id])
    return generate_club(ctx, WorldRng(seed), plan, cities, IdentityRegistry())


@cache
def _giants() -> ClubDraft:
    return _draft(make_generation_context(), "giants")


@pytest.mark.parametrize("key", ARCHETYPES)
def test_generate_club__team_rating_hits_the_archetype_target(key: str) -> None:
    ctx = make_generation_context()
    draft = _draft(ctx, key)
    seniors = [p for p in draft.players if not p.is_youth]
    rating = squad_strength(seniors, draft.club.default_tactics, ctx.tables.roles)
    assert abs(rating - draft.team_rating_target) <= TOLERANCE
    low, high = ctx.tables.clubs.archetypes[key].quality
    assert low - 1 <= rating <= high + 1


def test_generate_club__squad_has_twenty_five_seniors_and_eight_youth() -> None:
    draft = _giants()
    assert sum(not p.is_youth for p in draft.players) == 25
    assert sum(p.is_youth for p in draft.players) == 8
    counts = Counter(p.primary_position for p in draft.players if not p.is_youth)
    assert counts[Position.GK] == 3
    assert counts[Position.CB] == 4


def test_generate_club__shirt_numbers_are_unique_and_in_range() -> None:
    numbers = [p.squad_number for p in _giants().players]
    assert len(numbers) == len(set(numbers))
    assert all(n is not None and 1 <= n <= 99 for n in numbers)


def test_generate_club__keepers_wear_one_thirteen_thirty_one() -> None:
    keepers = [
        p.squad_number
        for p in _giants().players
        if p.primary_position is Position.GK and not p.is_youth
    ]
    assert sorted(n for n in keepers if n is not None) == [1, 13, 31]


def test_generate_club__everyone_has_a_contract_with_the_club() -> None:
    draft = _giants()
    assert all(
        p.contract is not None and p.contract.club_id == draft.club.id for p in draft.players
    )
    assert {e.player_id for e in draft.squad_entries} == {p.id for p in draft.players}


def test_generate_club__squad_roles_follow_ability_rank() -> None:
    draft = _giants()
    roles = Counter(p.contract.squad_role for p in draft.players if p.contract)
    assert roles[SquadRole.KEY] == 7
    assert roles[SquadRole.ROTATION] == 7
    assert roles[SquadRole.PROSPECT] == 8


@pytest.mark.parametrize("key", ARCHETYPES)
def test_generate_club__wage_bill_matches_the_archetype_ratio(key: str) -> None:
    ctx = make_generation_context()
    draft = _draft(ctx, key)
    bill = sum(p.contract.wage_weekly for p in draft.players if p.contract)
    ratio = bill / draft.club.finances.wage_budget_weekly
    low, high = ctx.tables.clubs.archetypes[key].wage_ratio
    assert low - 0.02 <= ratio <= high + 0.02


def test_generate_club__opening_ledger_equals_balance() -> None:
    draft = _giants()
    assert sum(entry.amount for entry in draft.ledger) == draft.club.finances.balance


def test_generate_club__academy_prospects_are_the_youth_players() -> None:
    draft = _giants()
    youth = {p.id for p in draft.players if p.is_youth}
    assert set(draft.club.academy.prospect_ids) == youth


def test_generate_club__manager_and_staff_belong_to_the_club() -> None:
    draft = _giants()
    assert draft.club.manager_id == draft.manager.id
    assert len(draft.club.staff_ids) == len(draft.staff) == 9


def test_generate_club__default_tactics_use_the_managers_formation() -> None:
    draft = _giants()
    assert draft.club.default_tactics.formation == draft.manager.preferred_formation


def test_generate_club__same_seed__identical() -> None:
    first = _draft(make_generation_context(), "grafters", seed=3)
    second = _draft(make_generation_context(), "grafters", seed=3)
    assert first.club.model_dump_json() == second.club.model_dump_json()
    assert [p.model_dump_json() for p in first.players] == [
        p.model_dump_json() for p in second.players
    ]


def test_generate_club__boom_and_bust_is_in_debt_and_overspending() -> None:
    draft = _draft(make_generation_context(), "boom_and_bust")
    assert draft.club.finances.debt > 0
    bill = sum(p.contract.wage_weekly for p in draft.players if p.contract)
    assert bill > draft.club.finances.wage_budget_weekly


def test_short_code_for__avoids_taken_codes() -> None:
    assert short_code_for("Kesh", set()) == "KES"
    assert short_code_for("Kesh", {"KES"}) == "KEH"
    assert short_code_for("Ab", {"ABA"}) != "ABA"
