"""``generate_world``: the pure function from a seed to a complete, coherent World."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from footystreams.domain.club import Club, Rivalry
from footystreams.domain.competition import Competition, MatchRules, Season
from footystreams.domain.ids import IdMint
from footystreams.domain.manager import Manager, ManagerStyle
from footystreams.domain.player import Player
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import ClubId, CompetitionId, PlayerId, Position, SeasonId
from footystreams.domain.world import World
from footystreams.seed.clubs.generator import ClubDraft, ClubPlan, generate_club
from footystreams.seed.clubs.identity import IdentityRegistry
from footystreams.seed.config import GeneratorConfig
from footystreams.seed.geography import generate_geography
from footystreams.seed.league_shape import plan_league
from footystreams.seed.managers.generator import ManagerSpec, generate_manager
from footystreams.seed.media import generate_crew
from footystreams.seed.names.book import NameBook
from footystreams.seed.players.context import GenerationContext
from footystreams.seed.players.generator import PlayerSpec, generate_player
from footystreams.seed.referees import generate_referees
from footystreams.seed.relations.graph import build_relationships
from footystreams.seed.static.tables import StaticTables, load_static_tables

UNEMPLOYED_MANAGERS = 4
UNEMPLOYED_QUALITY = (45, 60)
UNEMPLOYED_REPUTATION = (30, 55)


def _rivalries(
    ctx: GenerationContext, drafts: Sequence[ClubDraft]
) -> dict[ClubId, tuple[Rivalry, ...]]:
    """Rivalry rows for both sides of every archetype rivalry whose clubs exist."""
    by_archetype = {draft.archetype_key: draft.club for draft in drafts}
    found: dict[ClubId, list[Rivalry]] = {draft.club.id: [] for draft in drafts}
    for spec in ctx.tables.clubs.rivalries:
        first, second = by_archetype.get(spec.a), by_archetype.get(spec.b)
        if first is None or second is None:
            continue
        found[first.id].append(
            Rivalry(
                club_id=second.id, intensity=spec.intensity, origin=spec.origin, label=spec.label
            )
        )
        found[second.id].append(
            Rivalry(
                club_id=first.id, intensity=spec.intensity, origin=spec.origin, label=spec.label
            )
        )
    return {club_id: tuple(items) for club_id, items in found.items()}


def _free_agents(ctx: GenerationContext, rng: WorldRng) -> list[Player]:
    spec = ctx.tables.clubs.squad
    positions = [pos for pos in Position for _ in range(spec.senior_template.get(pos, 0))]
    regions = ctx.geography.regions()
    players = []
    for index in range(spec.free_agents):
        stream = rng.fork(f"free-agent:{index}")
        request = PlayerSpec(
            position=stream.fork("position").choice(positions),
            age=stream.fork("age").randint(*spec.free_agent_age),
            target_ability=stream.fork("ability").randint(*spec.free_agent_ability),
            club_id=None,
            region=stream.fork("region").choice(regions),
            club_reputation=0,
        )
        players.append(generate_player(request, ctx, stream))
    return players


def _unemployed_managers(ctx: GenerationContext, rng: WorldRng) -> list[Manager]:
    styles = sorted(style.value for style in ManagerStyle)
    managers = []
    for index in range(UNEMPLOYED_MANAGERS):
        stream = rng.fork(f"manager:{index}")
        spec = ManagerSpec(
            club_id=None,
            style=ManagerStyle(stream.fork("style").choice(styles)),
            quality=stream.fork("quality").randint(*UNEMPLOYED_QUALITY),
            reputation=stream.fork("reputation").randint(*UNEMPLOYED_REPUTATION),
            region=stream.fork("region").choice(ctx.geography.regions()),
        )
        managers.append(generate_manager(spec, ctx, stream))
    return managers


def _competition(ctx: GenerationContext, clubs: Sequence[Club]) -> tuple[Competition, Season]:
    league = ctx.tables.clubs.league
    competition = Competition(
        id=CompetitionId(ctx.ids.next("competition")),
        name=league.name,
        short_name=league.short_name,
        club_ids=tuple(sorted(club.id for club in clubs)),
        rules=MatchRules(),
    )
    season = Season(
        id=SeasonId(ctx.ids.next("season")),
        competition_id=competition.id,
        label=league.first_season_label,
        starts_on=dt.date.fromisoformat(league.season_start),
        ends_on=dt.date.fromisoformat(league.season_end),
        matchdays=2 * (len(clubs) - 1),
    )
    return competition, season


def _generate_clubs(
    ctx: GenerationContext, root: WorldRng, config: GeneratorConfig
) -> list[ClubDraft]:
    cities = list(ctx.geography.cities[ctx.geography.home.id])
    registry = IdentityRegistry()
    clubs = ctx.tables.clubs
    return [
        generate_club(
            ctx,
            root.fork(f"club:{slot.archetype_key}"),
            ClubPlan(slot.archetype_key, clubs.archetypes[slot.archetype_key], slot.quality),
            cities,
            registry,
        )
        for slot in plan_league(root, clubs, config.clubs)
    ]


def generate_world(
    seed: int, config: GeneratorConfig | None = None, tables: StaticTables | None = None
) -> World:
    """Generate a complete world: same seed and config, same World, byte for byte."""
    settings = config or GeneratorConfig()
    root = WorldRng(seed).fork("world")
    names, ids = NameBook.from_static(), IdMint()
    geography = generate_geography(root.fork("geography"), names, ids)
    ctx = GenerationContext(
        tables or load_static_tables(), names, ids, geography, settings.created_in_world
    )
    drafts = _generate_clubs(ctx, root, settings)
    free_agents = _free_agents(ctx, root.fork("free-agents"))
    spare_managers = _unemployed_managers(ctx, root.fork("spare-managers"))
    referees = generate_referees(ctx, root.fork("referees"))
    crew = generate_crew(ctx, root.fork("crew"))
    outcome = build_relationships(ctx, root.fork("relationships"), drafts, crew)
    rivalries = _rivalries(ctx, drafts)
    clubs = [
        draft.club.model_copy(update={"rivalries": rivalries[draft.club.id]}) for draft in drafts
    ]
    competition, season = _competition(ctx, clubs)
    players = [outcome.renamed.get(PlayerId(str(p.id)), p) for d in drafts for p in d.players]
    return World(
        world_seed=seed,
        created_in_world=settings.created_in_world,
        nations=tuple(sorted(geography.nations, key=lambda n: n.id)),
        cities=tuple(sorted((c for g in geography.cities.values() for c in g), key=lambda c: c.id)),
        competitions=(competition,),
        seasons=(season,),
        clubs=tuple(sorted(clubs, key=lambda club: club.id)),
        squad_entries=tuple(
            sorted(
                (e for d in drafts for e in d.squad_entries),
                key=lambda e: (e.club_id, e.squad_number),
            )
        ),
        players=tuple(sorted([*players, *free_agents], key=lambda p: p.id)),
        managers=tuple(sorted([*(d.manager for d in drafts), *spare_managers], key=lambda m: m.id)),
        staff=tuple(sorted((s for d in drafts for s in d.staff), key=lambda s: s.id)),
        referees=tuple(sorted(referees, key=lambda r: r.id)),
        media=tuple(sorted(crew, key=lambda m: m.id)),
        relationships=tuple(sorted(outcome.relationships, key=lambda r: r.id)),
        memories=(),
        ledger_opening=tuple(sorted((e for d in drafts for e in d.ledger), key=lambda e: e.id)),
    )
