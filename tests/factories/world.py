"""Builders for seed-layer inputs: a generation context with the real tables and geography."""

from __future__ import annotations

import datetime as dt
from functools import cache

from footystreams.domain.rng import WorldRng
from footystreams.seed.geography import generate_geography
from footystreams.seed.ids import IdMint
from footystreams.seed.names.book import NameBook
from footystreams.seed.players.context import GenerationContext
from footystreams.seed.static.tables import StaticTables, load_static_tables

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
