"""Season-end progression and weekly training micro-steps for one player (pure)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from footystreams.domain.attributes import attribute_map
from footystreams.domain.development import DevelopmentEntry
from footystreams.domain.injury import InjurySeverity
from footystreams.domain.player import Player
from footystreams.domain.ratings import compute_current_ability
from footystreams.domain.rng import WorldRng
from footystreams.domain.roles import RoleCatalog
from footystreams.domain.valuation import market_value_of
from footystreams.league.development import (
    ATTRIBUTE_MAX,
    ENTRY_CAUSE_SEASON,
    ENTRY_CAUSE_TRAINING,
    GROUPS,
    Conditions,
    applies,
    apply_changes,
    fit_potential,
    growth_factor,
    integer_change,
    journal,
    saturation,
    season_changes,
    with_journal,
)
from footystreams.league.development_config import DevelopmentConfig

WEEKS_PER_YEAR = 52
MEAN_SATURATION = 0.5  # typical room-to-grow factor of an attribute
POTENTIAL_MAX = 100
CAUSE_INJURY = "injury_setback"


@dataclass(frozen=True, slots=True)
class ProgressionInputs:
    """Static inputs of every progression call."""

    config: DevelopmentConfig
    roles: RoleCatalog
    today: dt.date


def refresh(player: Player, roles: RoleCatalog, today: dt.date) -> Player:
    """Recompute current ability and market value after attributes changed."""
    rated = player.model_copy(update={"ability_current": compute_current_ability(player, roles)})
    return rated.model_copy(update={"market_value": market_value_of(rated, today)})


def revise_potential(player: Player, inputs: ProgressionInputs, rng: WorldRng) -> Player:
    """A young player's ceiling sometimes moves up or down; it never drops below his ability."""
    config = inputs.config.potential
    age = player.age_on(inputs.today)
    if not config.min_age <= age <= config.max_age or not rng.bernoulli(config.chance):
        return player
    low, high = config.up if rng.bernoulli(0.5) else (-config.down[1], -config.down[0])
    potential = max(
        player.ability_current,
        min(POTENTIAL_MAX, player.ability_potential + rng.randint(low, high)),
    )
    return player.model_copy(update={"ability_potential": potential})


def _setback(player: Player, inputs: ProgressionInputs, rng: WorldRng) -> dict[str, dict[str, int]]:
    """Severe injuries that ended in the last year cost some physical points."""
    start = inputs.today - dt.timedelta(days=365)
    severe = [
        r
        for r in player.injury_history
        if r.severity is InjurySeverity.SEVERE and r.returned_on > start
    ]
    cost = sum(
        rng.fork(str(r.returned_on)).randint(0, inputs.config.progression.injury_setback_max)
        for r in severe
    )
    if not cost:
        return {}
    names = ("pace", "acceleration", "stamina")
    losses: dict[str, int] = {}
    for index in range(cost):
        name = names[index % len(names)]
        losses[name] = losses.get(name, 0) - 1
    return {"physical": losses}


def progress_season(
    player: Player, conditions: Conditions, inputs: ProgressionInputs, rng: WorldRng
) -> tuple[Player, tuple[DevelopmentEntry, ...]]:
    """The season-end step: age curve, training, playing time, noise, injuries, potential cap."""
    age = player.age_on(inputs.today)
    changes = season_changes(
        player, age, (conditions, inputs.config.progression), rng.fork("curve")
    )
    changes = fit_potential(player, changes, inputs.roles)
    entries = list(journal(changes, inputs.today, ENTRY_CAUSE_SEASON))
    moved = apply_changes(player, changes)
    setback = _setback(player, inputs, rng.fork("injury"))
    entries.extend(journal(setback, inputs.today, CAUSE_INJURY))
    moved = apply_changes(moved, setback)
    revised = revise_potential(
        refresh(moved, inputs.roles, inputs.today), inputs, rng.fork("potential")
    )
    return with_journal(revised, tuple(entries)), tuple(entries)


def _weekly_weights(
    player: Player, conditions: Conditions, inputs: ProgressionInputs
) -> dict[str, float]:
    """Expected points this week by group."""
    config = inputs.config.progression
    age = player.age_on(inputs.today)
    return {
        group: config.curves[group].growth_at(age)
        * growth_factor(player, conditions, group, config)
        * config.micro_share
        / WEEKS_PER_YEAR
        * len(attribute_map(getattr(player, group)))
        * MEAN_SATURATION
        for group in GROUPS
        if applies(group, player)
    }


def micro_step(
    player: Player, conditions: Conditions, inputs: ProgressionInputs, rng: WorldRng
) -> tuple[Player, tuple[DevelopmentEntry, ...]]:
    """A week of training: a few single-point gains, spread by group and by room to grow."""
    weights = _weekly_weights(player, conditions, inputs)
    points = integer_change(sum(weights.values()), 0.0, rng.fork("count"))
    if points <= 0:
        return player, ()
    changes: dict[str, dict[str, int]] = {}
    for index in range(points):
        pick = rng.fork(f"pick:{index}")
        group = pick.choice_weighted({g: w for g, w in weights.items() if w > 0})
        values = attribute_map(getattr(player, group))
        name = pick.choice_weighted({n: saturation(v) for n, v in sorted(values.items())})
        taken = changes.setdefault(group, {})
        if values[name] + taken.get(name, 0) < ATTRIBUTE_MAX:
            taken[name] = taken.get(name, 0) + 1
    changes = fit_potential(player, changes, inputs.roles)
    if not any(changes.values()):
        return player, ()
    entries = journal(changes, inputs.today, ENTRY_CAUSE_TRAINING)
    return with_journal(
        refresh(apply_changes(player, changes), inputs.roles, inputs.today), entries
    ), entries
