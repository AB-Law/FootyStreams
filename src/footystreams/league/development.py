"""Attribute progression: age curves, headroom, training, playing time, noise, journal.

Pure. ``progress_player`` returns the changed player and the journal entries that explain every
attribute point that moved, so a delta never appears without a cause. Ability can never rise
above potential: gains are trimmed one point at a time until it fits.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass

from footystreams.domain.attributes import attribute_map
from footystreams.domain.base import DomainModel
from footystreams.domain.development import DevelopmentEntry
from footystreams.domain.player import MAX_DEVELOPMENT_LOG, Player
from footystreams.domain.ratings import compute_current_ability
from footystreams.domain.rng import WorldRng
from footystreams.domain.roles import RoleCatalog
from footystreams.domain.types import Position
from footystreams.league.development_config import AgeCurve, ProgressionConfig

GROUPS = ("technical", "mental", "physical", "goalkeeping")
ATTRIBUTE_MIN, ATTRIBUTE_MAX = 1, 100
SATURATION_SPAN = 50.0  # attributes above 100 - span grow at a reduced rate
SATURATION_FLOOR = 0.2
MIDPOINT = 50.0
ENTRY_CAUSE_SEASON = "season_progression"
ENTRY_CAUSE_TRAINING = "training"


@dataclass(frozen=True, slots=True)
class Conditions:
    """What a player's year looked like for development: coaching per group and playing time."""

    training: Mapping[str, float]  # group -> 0..1 quality of facilities and coaching
    playing_time: float  # 0..1 share of a full season's minutes


def _lean(value: int) -> float:
    return (value - MIDPOINT) / MIDPOINT


def headroom(player: Player, config: ProgressionConfig) -> float:
    """1.0 while the player is far below potential, falling to 0.0 as ability meets it."""
    return max(
        0.0,
        min(1.0, (player.ability_potential - player.ability_current) / config.headroom_reference),
    )


def growth_factor(
    player: Player, conditions: Conditions, group: str, config: ProgressionConfig
) -> float:
    """Everything that scales the age curve's growth for one group (before attribute saturation)."""
    training = config.training_floor + (1 - config.training_floor) * conditions.training[group]
    playing = config.playing_time_floor + (1 - config.playing_time_floor) * conditions.playing_time
    professionalism = 1 + config.professionalism_weight * _lean(player.personality.professionalism)
    development = 1 + config.development_rate_weight * _lean(player.hidden.development_rate)
    return max(0.0, headroom(player, config) * training * playing * professionalism * development)


def decline_factor(player: Player, group: str, config: ProgressionConfig) -> float:
    """Natural fitness slows (or speeds) the decline of the physical group."""
    if group != "physical":
        return 1.0
    return max(0.0, 1 - config.fitness_decline_weight * _lean(player.physical.natural_fitness))


def saturation(value: int) -> float:
    """Room-to-grow factor of an attribute: elite values grow more slowly."""
    return max(SATURATION_FLOOR, min(1.0, (ATTRIBUTE_MAX - value) / SATURATION_SPAN))


def integer_change(expected: float, noise: float, rng: WorldRng) -> int:
    """Round an expected change to whole points with the remainder drawn as a chance."""
    value = expected + rng.normal(0.0, noise) if noise else expected
    whole = int(value // 1)
    return whole + (1 if rng.bernoulli(value - whole) else 0)


def applies(group: str, player: Player) -> bool:
    """The goalkeeping group only develops for goalkeepers."""
    return group != "goalkeeping" or player.primary_position is Position.GK


def group_changes(
    player: Player, group: str, expected: tuple[float, float], rng: WorldRng, noise: float
) -> dict[str, int]:
    """Whole-point changes per attribute of one group; ``expected`` is (growth, decline) a year."""
    growth, decline = expected
    model: DomainModel = getattr(player, group)
    changes: dict[str, int] = {}
    for name, value in sorted(attribute_map(model).items()):
        change = integer_change(growth * saturation(value) - decline, noise, rng.fork(name))
        change = max(ATTRIBUTE_MIN - value, min(ATTRIBUTE_MAX - value, change))
        if change:
            changes[name] = change
    return changes


def season_changes(
    player: Player,
    age: int,
    context: tuple[Conditions, ProgressionConfig],
    rng: WorldRng,
) -> dict[str, dict[str, int]]:
    """Proposed attribute changes by group for the season-end step."""
    conditions, config = context
    result: dict[str, dict[str, int]] = {}
    for group in GROUPS:
        if not applies(group, player):
            continue
        curve: AgeCurve = config.curves[group]
        growth = curve.growth_at(age) * growth_factor(player, conditions, group, config)
        expected = (
            growth * (1 - config.micro_share),
            curve.decline_at(age) * decline_factor(player, group, config),
        )
        changes = group_changes(player, group, expected, rng.fork(group), config.noise)
        if changes:
            result[group] = changes
    return result


def apply_changes(player: Player, changes: Mapping[str, Mapping[str, int]]) -> Player:
    """The player with the attribute changes applied (values stay within 1-100)."""
    updates: dict[str, DomainModel] = {}
    for group, deltas in changes.items():
        model: DomainModel = getattr(player, group)
        values = attribute_map(model)
        updates[group] = model.model_copy(
            update={
                name: max(ATTRIBUTE_MIN, min(ATTRIBUTE_MAX, values[name] + delta))
                for name, delta in deltas.items()
            }
        )
    return player.model_copy(update=updates)


def _ability(player: Player, roles: RoleCatalog) -> int:
    return compute_current_ability(player, roles)


def fit_potential(
    before: Player, changes: Mapping[str, Mapping[str, int]], roles: RoleCatalog
) -> dict[str, dict[str, int]]:
    """Trim the largest gains one point at a time until ability fits under potential."""
    trimmed = {group: dict(deltas) for group, deltas in changes.items()}
    while _ability(apply_changes(before, trimmed), roles) > before.ability_potential:
        gains = [
            (delta, group, name)
            for group, d in trimmed.items()
            for name, delta in d.items()
            if delta > 0
        ]
        if not gains:
            break
        _, group, name = max(gains)
        trimmed[group][name] -= 1
        if not trimmed[group][name]:
            del trimmed[group][name]
    return trimmed


def journal(
    changes: Mapping[str, Mapping[str, int]], today: dt.date, cause: str
) -> tuple[DevelopmentEntry, ...]:
    """One entry per attribute that moved, in group and attribute order."""
    return tuple(
        DevelopmentEntry(date=today, attr=name, delta=delta, cause=cause)
        for group in GROUPS
        for name, delta in sorted(changes.get(group, {}).items())
    )


def with_journal(player: Player, entries: tuple[DevelopmentEntry, ...]) -> Player:
    """Append entries, keeping the newest ``MAX_DEVELOPMENT_LOG``."""
    log = (*player.development_log, *entries)[-MAX_DEVELOPMENT_LOG:]
    return player.model_copy(update={"development_log": log})
