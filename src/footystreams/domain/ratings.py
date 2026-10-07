"""Pure player and team rating helpers (CA, profiles, XI strength)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from footystreams.domain.attributes import attribute_map
from footystreams.domain.base import DomainModel
from footystreams.domain.player import Player
from footystreams.domain.roles import RoleCatalog, RoleDefinition, RoleDutySpec
from footystreams.domain.types import AbilityScore, Duty, Position, RoleId

ABILITY_SCORE_MIN = 1
ABILITY_SCORE_MAX = 100
XI_SIZE = 11


def _flat_attributes(player: Player) -> Mapping[str, int]:
    merged: dict[str, int] = {}
    for group in (
        player.technical,
        player.mental,
        player.physical,
        player.goalkeeping,
        player.hidden,
    ):
        merged.update(attribute_map(group))
    return merged


def _competence_scale(player: Player, position: Position) -> float:
    return player.position_competence.get(position, 0) / 100.0


def _weighted_role_score(
    attrs: Mapping[str, int],
    spec: RoleDutySpec,
    competence_scale: float,
) -> float:
    total_weight = sum(spec.attr_weights.values())
    weighted = 0.0
    for name, weight in spec.attr_weights.items():
        value = attrs.get(name, 0)
        weighted += value * (weight / total_weight)
    return weighted * competence_scale


def role_rating(
    player: Player,
    role: RoleDefinition,
    duty: Duty,
) -> float:
    """Competence-scaled weighted attribute score for one role+duty."""
    spec = role.duties.get(duty)
    if spec is None:
        return 0.0
    return _weighted_role_score(
        _flat_attributes(player),
        spec,
        _competence_scale(player, role.position),
    )


def compute_current_ability(player: Player, catalog: RoleCatalog) -> AbilityScore:
    """Best role+duty fit across the catalog, clamped to AbilityScore."""
    best = 0.0
    attrs = _flat_attributes(player)
    for role in catalog.roles.values():
        scale = _competence_scale(player, role.position)
        for spec in role.duties.values():
            best = max(best, _weighted_role_score(attrs, spec, scale))
    score = round(best)
    return max(ABILITY_SCORE_MIN, min(ABILITY_SCORE_MAX, score))


def assigned_or_best_role_rating(
    player: Player,
    catalog: RoleCatalog,
    role_id: RoleId,
    duty: Duty,
) -> float:
    """Rate the assigned role+duty, else fall back to the player's best fit."""
    role = catalog.get(role_id)
    if role is not None and duty in role.duties:
        return role_rating(player, role, duty)
    return float(compute_current_ability(player, catalog))


def team_rating(
    starters: Sequence[tuple[Player, RoleId, Duty]],
    catalog: RoleCatalog,
) -> float:
    """Mean assigned-role rating of the XI (0-100).

    Each starter is rated on the lineup's role+duty when present in the
    catalog; otherwise the player's best-fit CA is used.
    """
    if len(starters) != XI_SIZE:
        msg = f"team_rating expects exactly {XI_SIZE} starters"
        raise ValueError(msg)
    total = sum(
        assigned_or_best_role_rating(player, catalog, role_id, duty)
        for player, role_id, duty in starters
    )
    return round(total / float(XI_SIZE), 4)


SIGNATURE_RULES: tuple[tuple[str, Mapping[str, int]], ...] = (
    ("elite_finisher", {"finishing": 85, "composure": 70}),
    ("engine", {"stamina": 85, "work_rate": 80}),
    ("aerial_threat", {"heading": 85, "jumping_reach": 80}),
    ("speedster", {"pace": 85, "acceleration": 80}),
    ("playmaker", {"vision": 85, "short_passing": 80}),
    ("ball_playing_defender", {"tackling": 75, "short_passing": 80, "composure": 75}),
    ("set_piece_specialist", {"set_piece_delivery": 85}),
)


def signature_skills(player: Player) -> tuple[str, ...]:
    """Rule-derived signature labels from attribute floors."""
    attrs = _flat_attributes(player)
    labels: list[str] = []
    for label, floors in SIGNATURE_RULES:
        if all(attrs.get(name, 0) >= floor for name, floor in floors.items()):
            labels.append(label)
    return tuple(labels)


def _group_mean(group: DomainModel) -> float:
    values = list(attribute_map(group).values())
    return round(sum(values) / len(values), 4)


def group_scores(player: Player) -> Mapping[str, float]:
    """Mean attribute per top-level group."""
    return {
        "technical": _group_mean(player.technical),
        "mental": _group_mean(player.mental),
        "physical": _group_mean(player.physical),
        "goalkeeping": _group_mean(player.goalkeeping),
    }


def all_role_ratings(player: Player, catalog: RoleCatalog) -> Mapping[str, AbilityScore]:
    """AbilityScore per ``role_id:duty`` key for every catalog entry."""
    result: dict[str, AbilityScore] = {}
    for role in catalog.roles.values():
        for duty in role.duties:
            score = round(role_rating(player, role, duty))
            clamped = max(ABILITY_SCORE_MIN, min(ABILITY_SCORE_MAX, score))
            result[f"{role.role_id}:{duty.value}"] = clamped
    return result


def position_ratings(player: Player, catalog: RoleCatalog) -> Mapping[Position, AbilityScore]:
    """Best role rating per position represented in the catalog."""
    best: dict[Position, int] = {}
    for role in catalog.roles.values():
        for duty in role.duties:
            score = round(role_rating(player, role, duty))
            clamped = max(ABILITY_SCORE_MIN, min(ABILITY_SCORE_MAX, score))
            previous = best.get(role.position, 0)
            if clamped > previous:
                best[role.position] = clamped
    return best
