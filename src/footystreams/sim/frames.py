"""Tracking frames: a deterministic snapshot of the 22 players and the ball every few seconds.

Frames are opt-in (`SimConfig.emit_frames`) and never change anything else: they draw no random
numbers and read the state only. Positions move in jumps at the engine's own step, so a frame
between two steps is the straight-line interpolation between the positions at the previous step
and the current one (docs/design/03 section 3, `frame`). The log with frames, minus the frames
and renumbered, is the log without them.
"""

from __future__ import annotations

from dataclasses import dataclass

from footystreams.domain.types import PlayerId
from footystreams.events.structure import FrameEvent, FramePlayer
from footystreams.sim.emit import EventEmitter, Meta
from footystreams.sim.geometry import distance_m
from footystreams.sim.mathx import clamp, lerp
from footystreams.sim.state import MatchState

PRECISION = 4
# A long moment can last far longer than the ball takes to move (a throw-in delay, a goal
# celebration). In one, the ball and the player it ends up with cover their distance at this speed
# and then wait, so a long moment shows a quick move and a hold, not a ball crawling for the span.
BALL_SPEED_MPS = 25.0
LONG_MOMENT_S = (
    5.0  # shorter moments move everything together, so the carrier stays among the others
)
MIN_TRAVEL_S = 0.4


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Where everyone and the ball were at one moment (absolute coordinates)."""

    t: float
    ball: tuple[float, float]
    carrier: PlayerId
    players: dict[PlayerId, tuple[float, float]]


def snapshot(state: MatchState) -> Snapshot:
    """Capture the positions of every player on the pitch and the ball."""
    return Snapshot(
        t=state.t_period,
        ball=(state.ball_x, state.ball_y),
        carrier=state.carrier.player_id,
        players={
            player.player_id: (player.x, player.y)
            for team in (state.home, state.away)
            for player in team.players
        },
    )


def _blend(
    start: tuple[float, float], end: tuple[float, float], fraction: float
) -> tuple[float, float]:
    return lerp(start[0], end[0], fraction), lerp(start[1], end[1], fraction)


class FrameRecorder:
    """Emits a frame event at every multiple of the interval inside a period."""

    def __init__(self, interval_s: int) -> None:
        """Start with no base; call `reset` at the start of each period."""
        self._interval = interval_s
        self._base: Snapshot | None = None
        self._next_t = interval_s
        self._last: dict[PlayerId, tuple[float, float]] = {}

    def reset(self, state: MatchState) -> None:
        """Begin a period: the base is the kick-off positions and the first frame is due."""
        self._base = snapshot(state)
        self._next_t = self._interval
        self._last = dict(self._base.players)

    def record(self, state: MatchState, emitter: EventEmitter) -> None:
        """Emit the frames due between the previous step and now, then rebase on now."""
        base = self._base
        if base is None:
            return
        current = snapshot(state)
        span = current.t - base.t
        travel = span
        if span > LONG_MOMENT_S:
            travel = max(MIN_TRAVEL_S, distance_m(*base.ball, *current.ball) / BALL_SPEED_MPS)
        while self._next_t <= current.t:
            elapsed = self._next_t - base.t
            fraction = elapsed / span if span > 0 else 1.0
            ball_fraction = min(1.0, elapsed / travel) if span > 0 else 1.0
            view = _FrameView(base, current, fraction, ball_fraction)
            self._emit(state, emitter, float(self._next_t), view)
            self._next_t += self._interval
        self._base = current

    def _emit(self, state: MatchState, emitter: EventEmitter, at: float, view: _FrameView) -> None:
        positions = view.positions()
        rows = []
        for team in (state.home, state.away):
            for player in team.players:
                x, y = positions[player.player_id]
                before = self._last.get(player.player_id, (x, y))
                speed = distance_m(before[0], before[1], x, y) / self._interval
                rows.append(
                    FramePlayer(
                        player_id=player.player_id,
                        x=round(clamp(x, 0.0, 1.0), PRECISION),
                        y=round(clamp(y, 0.0, 1.0), PRECISION),
                        speed_mps=round(speed, 1),
                        exhaustion=round(min(1.0, player.exhaustion), PRECISION),
                    )
                )
        self._last = positions
        ball = view.ball()
        saved = state.t_period
        state.t_period = at
        try:
            emitter.emit(
                state,
                FrameEvent,
                Meta(),
                ball_pos_x=round(clamp(ball[0], 0.0, 1.0), PRECISION),
                ball_pos_y=round(clamp(ball[1], 0.0, 1.0), PRECISION),
                carrier_id=view.carrier(),
                players=tuple(rows),
            )
        finally:
            state.t_period = saved


@dataclass(frozen=True, slots=True)
class _FrameView:
    """The interpolation between two snapshots at a fraction of the way."""

    start: Snapshot
    end: Snapshot
    fraction: float  # of the whole moment, for players walking to their places
    ball_fraction: float  # of the ball's own journey, for the ball and the player who gets it

    def positions(self) -> dict[PlayerId, tuple[float, float]]:
        """Return each player's interpolated position (new arrivals appear where they are)."""
        return {
            pid: _blend(
                self.start.players.get(pid, spot),
                spot,
                self.ball_fraction if pid == self.end.carrier else self.fraction,
            )
            for pid, spot in self.end.players.items()
        }

    def ball(self) -> tuple[float, float]:
        """Return the interpolated ball position."""
        return _blend(self.start.ball, self.end.ball, self.ball_fraction)

    def carrier(self) -> PlayerId:
        """The man on the ball: the old carrier until the step completes, then the new one."""
        return self.end.carrier if self.ball_fraction >= 1.0 else self.start.carrier
