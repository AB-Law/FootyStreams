"""Daily recovery: fatigue, fitness, morale drift, weekly sharpness decay and injury healing.

Pure. ``recover`` returns the player unchanged (the same object) when nothing moves, so the
stage only writes players who actually changed.
"""

from __future__ import annotations

import datetime as dt

from footystreams.domain.injury import InjuryRecord
from footystreams.domain.player import Player, PlayerStatus
from footystreams.league.config import RecoveryConfig

NEUTRAL_MORALE = 0.5
DECIMALS = 4


def _toward(value: float, target: float, step: float) -> float:
    """Move ``value`` towards ``target`` by at most ``step``."""
    if value < target:
        return min(target, value + step)
    return max(target, value - step)


def _healed(player: Player, today: dt.date) -> Player:
    """Clear an injury whose return date has come, keeping it in the history."""
    injury = player.current_injury
    if injury is None or injury.expected_return_on > today:
        return player
    record = InjuryRecord(
        type=injury.type,
        body_part=injury.body_part,
        severity=injury.severity,
        started_on=injury.started_on,
        returned_on=today,
        games_missed=injury.games_missed,
    )
    return player.model_copy(
        update={"current_injury": None, "injury_history": (*player.injury_history, record)}
    )


def recover(player: Player, today: dt.date, config: RecoveryConfig) -> Player:
    """One day of recovery: fatigue and morale settle, fitness returns, injuries heal."""
    if player.status is not PlayerStatus.ACTIVE:
        return player
    healed = _healed(player, today)
    fitness = healed.fitness
    if healed.current_injury is None:
        fitness = min(1.0, fitness + config.fitness_gain_rest_day)
    changes = {
        "fatigue": round(max(0.0, healed.fatigue - config.fatigue_rest_day), DECIMALS),
        "fitness": round(fitness, DECIMALS),
        "morale": round(
            _toward(healed.morale, NEUTRAL_MORALE, config.morale_drift_per_day), DECIMALS
        ),
    }
    if all(getattr(healed, key) == value for key, value in changes.items()):
        return healed
    return healed.model_copy(update=changes)


def decay_sharpness(player: Player, config: RecoveryConfig) -> Player:
    """The weekly loss of match sharpness for being idle, down to the floor (never up to it)."""
    if player.status is not PlayerStatus.ACTIVE or player.match_sharpness <= config.sharpness_floor:
        return player
    lowered = round(player.match_sharpness - config.sharpness_decay_idle_week, DECIMALS)
    return player.model_copy(update={"match_sharpness": max(config.sharpness_floor, lowered)})
