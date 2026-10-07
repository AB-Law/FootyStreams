"""Frozen copies of people for one match: what the simulator is allowed to see."""

from __future__ import annotations

import datetime as dt

from footystreams.domain.manager import Manager
from footystreams.domain.match import ManagerSnapshot
from footystreams.domain.mood import ResolvedMood
from footystreams.domain.player import Player
from footystreams.domain.snapshot import PlayerSnapshot
from footystreams.domain.types import ManagerId, PlayerId


def snapshot_player(player: Player, mood: ResolvedMood, today: dt.date) -> PlayerSnapshot:
    """The player as he walks out today: attributes, condition and the resolved mood.

    The match record stores this, so a match can be replayed and audited even after the player
    or his modifiers change.
    """
    return PlayerSnapshot(
        id=PlayerId(player.id),
        known_as=player.known_as,
        age=player.age_on(today),
        height_cm=player.height_cm,
        weight_kg=player.weight_kg,
        preferred_foot=player.preferred_foot,
        weak_foot=player.weak_foot,
        technical=player.technical,
        mental=player.mental,
        physical=player.physical,
        goalkeeping=player.goalkeeping,
        hidden=player.hidden,
        position_competence=player.position_competence,
        role_familiarity=player.role_familiarity,
        traits=player.traits,
        form=player.form,
        morale=player.morale,
        mood=mood,
        fitness=player.fitness,
        fatigue=player.fatigue,
        match_sharpness=player.match_sharpness,
        volatility=player.personality.volatility,
        sportsmanship=player.personality.sportsmanship,
        reputation=player.reputation,
        squad_number=player.squad_number,
        public_storylines=mood.public_storyline_keys,
    )


def snapshot_manager(manager: Manager) -> ManagerSnapshot:
    """The manager's sheet entry."""
    return ManagerSnapshot(
        id=ManagerId(manager.id),
        name=manager.known_as,
        philosophy=manager.philosophy,
        flexibility=manager.flexibility,
        sub_habits=manager.substitution_habits,
        tactical_knowledge=manager.attributes.tactical_knowledge,
        formation_proficiency=manager.formation_proficiency,
        fallback_formations=manager.fallback_formations,
    )
