"""Assemble the seed relationship graph for a whole world."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from footystreams.domain.media import MediaPersonality
from footystreams.domain.player import Player
from footystreams.domain.relationship import Relationship
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import EntityKind, PlayerId
from footystreams.seed.clubs.generator import ClubDraft
from footystreams.seed.players.context import GenerationContext
from footystreams.seed.relations import media, squads
from footystreams.seed.relations.builder import RelationshipBuilder
from footystreams.seed.relations.kin import KinPair, make_kin


@dataclass(frozen=True, slots=True)
class RelationshipOutcome:
    """The graph, plus any player renamed to share a surname with a relative."""

    relationships: tuple[Relationship, ...]
    renamed: Mapping[PlayerId, Player]


def _club_ties(
    ctx: GenerationContext, builder: RelationshipBuilder, rng: WorldRng, draft: ClubDraft
) -> None:
    seniors = [p for p in draft.players if not p.is_youth]
    youth = [p for p in draft.players if p.is_youth]
    squads.friendships(rng.fork("friends"), builder, seniors, ctx.today)
    squads.mentors(rng.fork("mentors"), builder, (seniors, youth), ctx.today)
    squads.rivals(rng.fork("rivals"), builder, draft.players)
    squads.manager_ties(rng.fork("manager"), builder, draft, seniors)


def _derby_managers(
    ctx: GenerationContext, builder: RelationshipBuilder, drafts: Sequence[ClubDraft]
) -> None:
    by_archetype = {draft.archetype_key: draft for draft in drafts}
    for rivalry in ctx.tables.clubs.rivalries:
        first, second = by_archetype.get(rivalry.a), by_archetype.get(rivalry.b)
        if first is not None and second is not None:
            builder.add(
                "rival",
                builder.ref(EntityKind.MANAGER, first.manager.id),
                builder.ref(EntityKind.MANAGER, second.manager.id),
                rivalry.intensity,
                valence=-rivalry.intensity / 2,
            )


def _kin(
    ctx: GenerationContext, builder: RelationshipBuilder, rng: WorldRng, drafts: Sequence[ClubDraft]
) -> KinPair | None:
    home = ctx.geography.home.id
    for draft in rng.shuffled(list(drafts)):
        local = [p for p in draft.players if p.nationality == home]
        pair = make_kin(rng, builder, local, ctx.names)
        if pair is not None:
            return pair
    return None


def build_relationships(
    ctx: GenerationContext,
    rng: WorldRng,
    drafts: Sequence[ClubDraft],
    crew: Sequence[MediaPersonality],
) -> RelationshipOutcome:
    """Squad friendships, mentors, rivals, manager trust, derby managers, kin and media ties."""
    builder = RelationshipBuilder(ctx.ids, ctx.today)
    for draft in drafts:
        _club_ties(ctx, builder, rng.fork(f"club:{draft.club.id}"), draft)
    _derby_managers(ctx, builder, drafts)
    pair = _kin(ctx, builder, rng.fork("kin"), drafts)
    named = dict(zip(sorted(ctx.tables.media.crew), crew, strict=True))
    media.crew_ties(builder, named)
    media.club_affinities(rng.fork("affinity"), builder, named, [d.club for d in drafts])
    everyone = [p for draft in drafts for p in draft.players]
    media.favourite_players(rng.fork("favourites"), builder, crew, everyone)
    renamed = {PlayerId(str(pair.relative.id)): pair.relative} if pair else {}
    return RelationshipOutcome(builder.rows(), renamed)
