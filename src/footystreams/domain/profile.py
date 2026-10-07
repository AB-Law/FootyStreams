"""Derived PlayerProfile view (never stored)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

from footystreams.domain.attributes import attribute_map
from footystreams.domain.base import DomainModel, UsageTag
from footystreams.domain.player import Player
from footystreams.domain.ratings import (
    all_role_ratings,
    group_scores,
    position_ratings,
    signature_skills,
)
from footystreams.domain.roles import RoleCatalog
from footystreams.domain.types import AbilityScore, Position

STD_EPSILON = 1e-9
RELIABLE_CONSISTENCY = 70
STREAKY_CONSISTENCY = 40
MAX_EXTREMES = 5
Z_STRENGTH = 1.0


class PlayerProfile(DomainModel):
    """What a player is good at — derived from attributes and the role catalog."""

    __usage__: ClassVar[Mapping[str, UsageTag]] = {
        "group_scores": "L",
        "role_ratings": "S",
        "position_ratings": "S",
        "strengths": "R",
        "weaknesses": "R",
        "signature_skills": "R",
        "archetype_label": "R",
        "volatility_label": "R",
    }

    group_scores: Mapping[str, float]
    role_ratings: Mapping[str, AbilityScore]
    position_ratings: Mapping[Position, AbilityScore]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    signature_skills: tuple[str, ...]
    archetype_label: str
    volatility_label: str


def _within_player_extremes(player: Player) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Top/bottom attributes by within-player z-score (no league distribution yet)."""
    values: dict[str, int] = {}
    for group in (player.technical, player.mental, player.physical):
        values.update(attribute_map(group))
    if not values:
        return (), ()
    mean = sum(values.values()) / len(values)
    variance = sum((value - mean) ** 2 for value in values.values()) / len(values)
    std = variance**0.5
    if std < STD_EPSILON:
        return (), ()
    ranked = sorted(
        ((name, (value - mean) / std) for name, value in values.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    strengths = tuple(name for name, z in ranked if z >= Z_STRENGTH)[:MAX_EXTREMES]
    weaknesses = tuple(name for name, z in reversed(ranked) if z <= -Z_STRENGTH)[:MAX_EXTREMES]
    return strengths, weaknesses


def _volatility_label(player: Player) -> str:
    consistency = player.hidden.consistency
    if consistency >= RELIABLE_CONSISTENCY:
        return "reliable"
    if consistency <= STREAKY_CONSISTENCY:
        return "streaky"
    return "mixed"


def build_profile(player: Player, catalog: RoleCatalog) -> PlayerProfile:
    """Derive the full PlayerProfile for UI, lineup AI and commentary hooks."""
    strengths, weaknesses = _within_player_extremes(player)
    return PlayerProfile(
        group_scores=group_scores(player),
        role_ratings=all_role_ratings(player, catalog),
        position_ratings=position_ratings(player, catalog),
        strengths=strengths,
        weaknesses=weaknesses,
        signature_skills=signature_skills(player),
        archetype_label=player.primary_position.value,
        volatility_label=_volatility_label(player),
    )
