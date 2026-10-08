"""The seeded ``WorldEventGenerator``: life events that happen around players, without an LLM.

Every player rolls independently each day from his own stream (``fork(player_id)``), so adding
or removing players never changes anyone else's luck. A hit creates a ``WorldEvent`` (the news
feed entry) and the ``StateModifier`` that puts it on the pitch (docs/design/07 section 3.2).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence

from footystreams.domain.ids import derive_id
from footystreams.domain.mood import (
    ModifierSource,
    ModifierVisibility,
    StateKind,
    StateModifier,
    WorldEvent,
)
from footystreams.domain.player import Player, PlayerStatus
from footystreams.domain.rng import WorldRng
from footystreams.domain.types import EntityKind, EntityRef, Id
from footystreams.league.config import WorldEventsConfig
from footystreams.league.delta import WorldDelta
from footystreams.league.modifiers import ModifierSpec, new_modifier
from footystreams.league.mood_config import MoodConfig

TRAIT_MIDPOINT = 50.0
TRAIT_SPAN = 50.0
EVENT_KIND: Mapping[StateKind, str] = {
    StateKind.MEDIA_STORM: "media_story",
    StateKind.MANAGER_ROW: "bust_up",
    StateKind.DRESSING_ROOM_ROW: "bust_up",
    StateKind.PERSONAL_TURMOIL: "personal_matter",
    StateKind.FAMILY_MATTER: "personal_matter",
    StateKind.HOMESICKNESS: "personal_matter",
    StateKind.FAN_ABUSE: "fan_incident",
}


def _lean(score: int) -> float:
    """How far a 0-100 trait sits from the middle, in [-1, 1]."""
    return (score - TRAIT_MIDPOINT) / TRAIT_SPAN


def _hazard(player: Player, config: WorldEventsConfig) -> float:
    """The chance of at least one life event in a roll's window: higher for volatile players."""
    scale = 1.0 + config.volatility_weight * _lean(player.personality.volatility)
    daily = min(1.0, max(0.0, config.daily_hazard * scale))
    return 1.0 - (1.0 - daily) ** config.roll_interval_days


def _kind_weights(player: Player, config: WorldEventsConfig) -> dict[StateKind, float]:
    """Configured weights, with media storms favouring players who talk to the media."""
    weights: dict[StateKind, float] = {}
    for name, weight in sorted(config.kind_weights.items()):
        kind = StateKind(name)
        boost = 1.0 + config.media_weight * _lean(player.personality.media_openness)
        weights[kind] = weight * max(0.0, boost) if kind is StateKind.MEDIA_STORM else weight
    return weights


def _event(
    player: Player, kind: StateKind, today: dt.date, visibility: ModifierVisibility
) -> WorldEvent:
    owner = EntityRef(kind=EntityKind.PLAYER, id=Id(str(player.id)))
    club = (
        EntityRef(kind=EntityKind.CLUB, id=Id(str(player.contract.club_id)))
        if player.contract
        else None
    )
    return WorldEvent(
        id=Id(derive_id("world_event", player.id, today.isoformat(), kind.value)),
        date=today,
        kind=EVENT_KIND[kind],
        participants=(owner, club) if club else (owner,),
        facts={"state": kind.value},
        visibility=visibility,
        origin="generator",
    )


def _life_event(
    player: Player, rng: WorldRng, today: dt.date, configs: tuple[WorldEventsConfig, MoodConfig]
) -> tuple[WorldEvent, StateModifier]:
    config, mood = configs
    kind = rng.choice_weighted(_kind_weights(player, config))
    low_days, high_days = config.duration_days
    low_magnitude, high_magnitude = config.magnitude
    visibility = (
        ModifierVisibility.PUBLIC if mood.kinds[kind.value].public else ModifierVisibility.PRIVATE
    )
    event = _event(player, kind, today, visibility)
    spec = ModifierSpec(
        kind,
        player.id,
        rng.uniform(low_magnitude, high_magnitude),
        ModifierSource(origin="world_event", world_event_id=event.id),
        days=rng.randint(low_days, high_days),
    )
    modifier = new_modifier(spec, today, mood)
    return event, modifier


def generate_life_events(
    players: Sequence[Player],
    today: dt.date,
    rng: WorldRng,
    configs: tuple[WorldEventsConfig, MoodConfig],
) -> WorldDelta:
    """The day's life events for ``players`` (retired and club-less players are skipped)."""
    events: list[WorldEvent] = []
    modifiers: list[StateModifier] = []
    for player in sorted(players, key=lambda item: item.id):
        if player.status is not PlayerStatus.ACTIVE or player.contract is None:
            continue
        stream = rng.fork(f"{today.isoformat()}:{player.id}")
        if stream.bernoulli(_hazard(player, configs[0])):
            event, modifier = _life_event(player, stream, today, configs)
            events.append(event)
            modifiers.append(modifier)
    return WorldDelta(world_events=tuple(events), modifiers=tuple(modifiers))
