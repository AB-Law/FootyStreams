"""Play: the bundle every resolver works with, plus possession and duration helpers.

`Play` groups the live state, the `play` random stream, the config and the emitter so resolvers
take one argument instead of four. `take_possession` is the only way the ball changes hands.
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.types import PlayerId
from footystreams.events.base import Participant
from footystreams.sim.config import SimConfig
from footystreams.sim.emit import EventEmitter, participant
from footystreams.sim.geometry import CENTRE
from footystreams.sim.mathx import signed_unit
from footystreams.sim.rng import SimRng
from footystreams.sim.state import MatchState, PlayerState, TeamState


@dataclass(slots=True)
class Play:
    """Everything one resolver needs: state, the `play` stream, config and the event log."""

    state: MatchState
    rng: SimRng
    cfg: SimConfig
    emit: EventEmitter


def take_possession(state: MatchState, player: PlayerState, x: float, y: float) -> None:
    """Give the ball to `player` at an absolute point; a change of side starts a new chain."""
    if player.side != state.carrier.side:
        state.chain += 1
        state.chain_started_at = state.elapsed_s
        state.last_turnover_s = state.elapsed_s
        state.assist_from = None
    state.carrier = player
    player.x, player.y = x, y
    state.ball_x, state.ball_y = x, y


def action_duration(play: Play, base_s: float) -> float:
    """Return how long an action takes: base x tempo scale x (1 +- noise); consumes one draw."""
    tempo = play.state.attackers.view.tempo
    scale = 1.0 + play.cfg.tempo.tempo_swing * (CENTRE - tempo)
    spread = play.cfg.tempo.noise * signed_unit(play.rng.u())
    return base_s * scale * (1.0 + spread)


def label(team: TeamState, player_id: PlayerId) -> str:
    """Return a terse `Name (CODE)` label for headlines."""
    return f"{team.sheet.squad[player_id].known_as} ({team.sheet.club.short_code})"


def actor(player: PlayerState, role: str) -> Participant:
    """Build a participant entry for a player state."""
    return participant(player.player_id, role)
