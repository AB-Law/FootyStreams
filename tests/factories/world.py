"""Builders for seed-layer inputs: a generation context with the real tables and geography."""

from __future__ import annotations

import datetime as dt
from functools import cache

from footystreams.domain.ids import IdMint
from footystreams.domain.rng import WorldRng
from footystreams.domain.world import World
from footystreams.seed.config import GeneratorConfig
from footystreams.seed.geography import generate_geography
from footystreams.seed.names.book import NameBook
from footystreams.seed.names.gates import normalise_list
from footystreams.seed.players.context import GenerationContext
from footystreams.seed.static.files import read_text_lines
from footystreams.seed.static.tables import StaticTables, load_static_tables
from footystreams.seed.world_gen import generate_world
from footystreams.verify import WorldChecks, WorldTargets

WORLD_START = dt.date(2031, 7, 1)


@cache
def cached_static_tables() -> StaticTables:
    """The static tables are immutable, so tests share one load."""
    return load_static_tables()


def make_generation_context(seed: int = 1, today: dt.date = WORLD_START) -> GenerationContext:
    """A fresh context over the real static tables, names and a generated geography."""
    names = NameBook.from_static()
    ids = IdMint()
    geography = generate_geography(WorldRng(seed).fork("geography"), names, ids)
    return GenerationContext(
        tables=cached_static_tables(), names=names, ids=ids, geography=geography, today=today
    )


@cache
def make_world(seed: int = 1, clubs: int = 8) -> World:
    """A generated world; worlds are immutable, so every test in the run shares one per seed."""
    return generate_world(seed, GeneratorConfig(clubs=clubs), cached_static_tables())


def make_world_checks() -> WorldChecks:
    """The static tables and denylist the world checks read."""
    tables = cached_static_tables()
    return WorldChecks(
        roles=tables.roles,
        formations=tables.formations,
        denylist=normalise_list(read_text_lines("denylist.txt")),
    )


def make_world_targets() -> WorldTargets:
    """Thresholds from the committed league tables, as the CLI builds them."""
    league = cached_static_tables().clubs.league
    return WorldTargets(
        min_team_gap=league.min_gap,
        max_team_gap=league.max_gap,
        min_adjacent_gap=league.min_adjacent_gap,
    )
