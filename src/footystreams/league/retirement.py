"""Retirement: chance by age and ability; retired players leave the pool but stay on record."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from footystreams.domain.ids import derive_id
from footystreams.domain.mood import ModifierVisibility, WorldEvent
from footystreams.domain.player import CareerStint, Player, PlayerStatus, SquadStatus
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import EntityKind, EntityRef, Id
from footystreams.league.development_config import RetirementConfig


def retirement_chance(
    player: Player, mean_ability: float, today: dt.date, config: RetirementConfig
) -> float:
    """Yearly chance: the age's base hazard, higher for weaker players, never above 1."""
    base = config.hazard_at(player.age_on(today))
    if base == 0.0:
        return 0.0
    gap = mean_ability - player.ability_current
    scale = max(config.min_hazard_multiplier, 1.0 + config.ability_weight * gap)
    return min(1.0, base * scale)


def retired(player: Player, today: dt.date) -> Player:
    """The player after retiring: no contract, no club, kept for history."""
    return player.model_copy(
        update={
            "status": PlayerStatus.RETIRED,
            "squad_status": SquadStatus.FREE_AGENT,
            "contract": None,
            "current_injury": None,
            "suspension": None,
            "career_history": _close_spell(player, today),
        }
    )


def _close_spell(player: Player, today: dt.date) -> tuple[CareerStint, ...]:
    return tuple(
        stint.model_copy(update={"to_date": today}) if stint.to_date is None else stint
        for stint in player.career_history
    )


def retirement_news(player: Player, today: dt.date) -> WorldEvent:
    """The feed entry for a retirement."""
    return WorldEvent(
        id=Id(derive_id("world_event", player.id, today.isoformat(), "retirement")),
        date=today,
        kind="retirement",
        participants=(EntityRef(kind=EntityKind.PLAYER, id=Id(player.id)),),
        facts={"age": player.age_on(today), "ability": player.ability_current},
        visibility=ModifierVisibility.PUBLIC,
        origin="rule",
    )


def choose_retirements(
    players: Sequence[Player], today: dt.date, config: RetirementConfig, rng: WorldRng
) -> list[Player]:
    """Who retires this year; each player rolls on his own stream."""
    active = [
        p for p in players if p.status is PlayerStatus.ACTIVE or p.status is PlayerStatus.FREE_AGENT
    ]
    if not active:
        return []
    mean = sum(p.ability_current for p in active) / len(active)
    return [
        p
        for p in sorted(active, key=lambda item: item.id)
        if rng.fork(p.id).bernoulli(retirement_chance(p, mean, today, config))
    ]
