"""Cards: the referee's booking decision and what a dismissal does to the pitch.

A yellow needs severity above a threshold that falls with the referee's card tendency and
strictness; a straight red needs very high severity or a denied goal-scoring chance; a second
yellow is a red. A side is never reduced below `min_players`: past that point the referee shows
no further cards (a defined rule, not an accident; docs/design/10 section 4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from footystreams.domain.types import Position
from footystreams.events.discipline import CardEvent
from footystreams.sim.actions.setpieces import restart_delay
from footystreams.sim.config_rules import DisciplineConfig
from footystreams.sim.discipline import Contact
from footystreams.sim.emit import Meta
from footystreams.sim.geometry import CENTRE
from footystreams.sim.play import Play, actor, label
from footystreams.sim.referee import RefereeProfile
from footystreams.sim.state import Line, PlayerState, TeamState

CardColour = Literal["yellow", "red", "second_yellow"]
KEEPER_BASE = (0.04, 0.5)  # an emergency keeper stands on the goalkeeper's slot


@dataclass(frozen=True, slots=True)
class CardDecision:
    """The card the referee shows and why."""

    colour: CardColour
    reason: str


def yellow_threshold(profile: RefereeProfile, cfg: DisciplineConfig) -> float:
    """Return the severity above which this referee books a foul."""
    return (
        cfg.yellow_base
        - cfg.yellow_tendency_swing * (profile.card_tendency - CENTRE)
        - cfg.yellow_strictness_swing * (profile.strictness - CENTRE)
    )


def decide_card(play: Play, offender: PlayerState, contact: Contact) -> CardDecision | None:
    """Decide whether and which card follows a called foul (one draw only for a denied chance)."""
    cfg = play.cfg.discipline
    if len(play.state.team(offender.side).players) <= cfg.min_players:
        return None
    if contact.denies_opportunity and play.discipline.u() < cfg.dogso_red_share:
        return CardDecision("red", "denying_opportunity")
    if contact.severity > cfg.red_threshold:
        return CardDecision("red", "violent_conduct")
    threshold = yellow_threshold(play.referee, cfg)
    if offender.yellow_cards >= 1:
        if contact.severity > threshold + cfg.second_booking_margin:
            return CardDecision("second_yellow", "second_yellow")
        return None
    return CardDecision("yellow", "foul") if contact.severity > threshold else None


def dismiss(team: TeamState, player: PlayerState) -> None:
    """Remove a sent-off player from the pitch; an outfielder takes over in goal if needed."""
    remove_from_pitch(team, player, team.sent_off)


def remove_from_pitch(team: TeamState, player: PlayerState, into: list[PlayerState]) -> None:
    """Take a player off the pitch without a replacement; an outfielder keeps goal if needed."""
    team.players.remove(player)
    into.append(player)
    if player.position is Position.GK and team.players:
        stand_in = max(team.players, key=lambda mate: (mate.skills.handling, -mate.slot))
        stand_in.position, stand_in.line = Position.GK, Line.KEEPER
        stand_in.base_x, stand_in.base_y = KEEPER_BASE


def show_card(play: Play, offender: PlayerState, contact: Contact, foul_id: str) -> float:
    """Show the card (if any) after a foul; return the stoppage seconds it costs."""
    decision = decide_card(play, offender, contact)
    if decision is None:
        return 0.0
    state = play.state
    team = state.team(offender.side)
    meta = Meta(
        team=offender.side,
        participants=(actor(offender, "booked"),),
        pos=(offender.x, offender.y),
        caused_by=foul_id,
        headline=f"{decision.colour.replace('_', ' ')} card: {label(team, offender.player_id)}",
    )
    if decision.colour == "yellow":
        offender.yellow_cards += 1
    else:
        if state.assist_from is offender:
            state.assist_from = None
        # Dismiss first: like the score on a goal, the men count in a card's context is "after".
        dismiss(team, offender)
    play.emit.emit(
        state,
        CardEvent,
        meta,
        player_id=offender.player_id,
        colour=decision.colour,
        reason=decision.reason,
    )
    cfg = play.cfg.discipline
    seconds = restart_delay(play, cfg.card_s, cfg.card_spread_s)
    state.stoppage_s += seconds
    return seconds
