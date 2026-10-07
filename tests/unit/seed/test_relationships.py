from __future__ import annotations

from collections import Counter
from functools import cache

from footystreams.domain.rng import WorldRng
from footystreams.domain.types import EntityKind
from footystreams.seed.clubs.generator import ClubDraft, ClubPlan, generate_club
from footystreams.seed.clubs.identity import IdentityRegistry
from footystreams.seed.media import generate_crew
from footystreams.seed.players.context import GenerationContext
from footystreams.seed.relations.builder import SYMMETRIC_KINDS, RelationshipBuilder
from footystreams.seed.relations.graph import RelationshipOutcome, build_relationships
from tests.factories.world import WORLD_START, make_generation_context

LEAGUE_ARCHETYPES = ("giants", "challengers", "old_money", "grafters")


def _world_slice(seed: int = 1) -> tuple[GenerationContext, list[ClubDraft], RelationshipOutcome]:
    ctx = make_generation_context(seed)
    cities = list(ctx.geography.cities[ctx.geography.home.id])
    registry = IdentityRegistry()
    drafts = []
    for key in LEAGUE_ARCHETYPES:
        archetype = ctx.tables.clubs.archetypes[key]
        plan = ClubPlan(key, archetype, sum(archetype.quality) / 2)
        drafts.append(generate_club(ctx, WorldRng(seed).fork(key), plan, cities, registry))
    crew = generate_crew(ctx, WorldRng(seed).fork("crew"))
    return ctx, drafts, build_relationships(ctx, WorldRng(seed).fork("rel"), drafts, crew)


@cache
def _cached() -> tuple[GenerationContext, list[ClubDraft], RelationshipOutcome]:
    return _world_slice()


def test_relationships__no_self_links_and_ids_are_unique() -> None:
    _, _, outcome = _cached()
    ids = [r.id for r in outcome.relationships]
    assert len(ids) == len(set(ids))
    assert all(r.a != r.b for r in outcome.relationships)


def test_relationships__symmetric_kinds_are_in_canonical_order() -> None:
    _, _, outcome = _cached()
    symmetric = [r for r in outcome.relationships if r.kind in SYMMETRIC_KINDS]
    assert symmetric
    assert all(r.a.id < r.b.id for r in symmetric)


def test_relationships__no_duplicate_pairs() -> None:
    _, _, outcome = _cached()
    keys = [(r.kind, r.a.id, r.b.id) for r in outcome.relationships]
    assert len(keys) == len(set(keys))


def test_relationships__every_endpoint_exists_in_the_world() -> None:
    _, drafts, outcome = _cached()
    known: set[str] = {
        ctx_id for draft in drafts for ctx_id in (str(draft.club.id), str(draft.manager.id))
    }
    known |= {str(p.id) for draft in drafts for p in draft.players}
    media_ids = {r.a.id for r in outcome.relationships if r.a.kind is EntityKind.MEDIA}
    endpoints = {e.id for r in outcome.relationships for e in (r.a, r.b)}
    assert endpoints - known - media_ids == set()


def test_relationships__each_club_has_friendships_mentors_and_manager_trust() -> None:
    _, drafts, outcome = _cached()
    for draft in drafts:
        player_ids = {str(p.id) for p in draft.players}
        kinds = Counter(
            r.kind for r in outcome.relationships if r.a.id in player_ids and r.b.id in player_ids
        )
        assert kinds["friend"] >= 6
        assert kinds["mentor_of"] >= 1
        trust = [
            r for r in outcome.relationships if r.kind == "trust" and r.a.id == draft.manager.id
        ]
        assert len(trust) == 7  # six key players and the board


def test_relationships__mentors_pair_a_veteran_with_a_youth_prospect() -> None:
    _, drafts, outcome = _cached()
    by_id = {str(p.id): p for draft in drafts for p in draft.players}
    mentor_rows = [r for r in outcome.relationships if r.kind == "mentor_of" and r.a.id in by_id]
    assert mentor_rows
    for row in mentor_rows:
        assert by_id[row.a.id].age_on(WORLD_START) >= 30
        assert by_id[row.b.id].is_youth


def test_relationships__derby_managers_are_rivals() -> None:
    _, drafts, outcome = _cached()
    managers = {d.archetype_key: str(d.manager.id) for d in drafts}
    pair = sorted([managers["giants"], managers["challengers"]])
    assert any(r.kind == "rival" and [r.a.id, r.b.id] == pair for r in outcome.relationships)


def test_relationships__local_hero_has_one_adored_and_one_disliked_club() -> None:
    _, _, outcome = _cached()
    club_rows = [
        r
        for r in outcome.relationships
        if r.b.kind is EntityKind.CLUB and r.a.kind is EntityKind.MEDIA
    ]
    assert Counter(r.kind for r in club_rows) == {"admires": 1, "dislikes": 1}


def test_relationships__every_crew_member_has_a_favourite_and_a_pet_hate() -> None:
    _, _, outcome = _cached()
    rows = [
        r
        for r in outcome.relationships
        if r.a.kind is EntityKind.MEDIA and r.b.kind is EntityKind.PLAYER
    ]
    assert Counter(r.kind for r in rows) == {"admires": 11, "dislikes": 11}


def test_relationships__kin_share_a_surname_but_not_a_known_as() -> None:
    _, drafts, outcome = _cached()
    family = [r for r in outcome.relationships if r.kind == "family"]
    assert len(family) <= 1
    for row in family:
        relative = outcome.renamed[next(k for k in outcome.renamed if k in {row.b.id, row.a.id})]
        elder_id = row.a.id if row.b.id == relative.id else row.b.id
        elder = next(p for d in drafts for p in d.players if p.id == elder_id)
        assert relative.last_name == elder.last_name
        assert relative.known_as != elder.known_as


def test_builder__self_links_and_duplicates_are_dropped() -> None:
    ctx = make_generation_context()
    builder = RelationshipBuilder(ctx.ids, WORLD_START)
    a = builder.ref(EntityKind.PLAYER, "plr_00001")
    b = builder.ref(EntityKind.PLAYER, "plr_00002")
    assert not builder.add("friend", a, a, 0.5)
    assert builder.add("friend", b, a, 0.5)
    assert not builder.add("friend", a, b, 0.7)
    assert len(builder.rows()) == 1
    assert builder.rows()[0].a == a
