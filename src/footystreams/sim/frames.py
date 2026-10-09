"""Tracking frames: a deterministic snapshot of the 22 players and the ball every few seconds.

Frames are opt-in (`SimConfig.emit_frames`) and never change anything else: they draw no random
numbers and read the state only. Positions move in jumps at the engine's own step, so a frame
between two steps is the straight-line interpolation between the positions at the previous step
and the current one (docs/design/03 section 3, `frame`). The log with frames, minus the frames
and renumbered, is the log without them.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

from footystreams.domain.types import PlayerId
from footystreams.events.structure import FrameEvent, FramePlayer
from footystreams.sim.emit import EventEmitter, Meta
from footystreams.sim.geometry import PITCH_LENGTH_M, PITCH_WIDTH_M, distance_m
from footystreams.sim.mathx import clamp, lerp
from footystreams.sim.state import Keyframe, MatchState

PRECISION = 4
# A moment is one action: the man on the ball holds it, then plays it. The sim has him standing
# still for the whole of it and the ball jumping to the next man, so frames show it as it looks:
# he jogs on with the ball for the hold (up to a few metres), then it travels at ball speed and he
# drifts back to where the sim has him. A long moment (a throw-in delay, a celebration) shows the
# ball arriving first and then the wait, not a ball crawling for the whole span.
BALL_SPEED_MPS = 25.0
LONG_MOMENT_S = 5.0
MIN_TRAVEL_S = 0.4
CARRY_SPEED_MPS = 4.5
MAX_CARRY_M = 7.0
_EPSILON = 1e-9  # a ball that lands at the very end of the moment has landed
CARRY_SHARE = 0.5  # of the pass length: a short pass is not a reason to run most of the way
# The sim places players where an action ends, so a restart or a won ball can move one across the
# pitch in a single step. A frame never shows that: he runs there, at no more than a sprinter's
# pace, and until he has reached the ball it is loose rather than "carried" by him.
MAX_SPEED_MPS = 9.0
# A pass longer than this leaves the ground: its height is a parabola peaking at LOFT_PER_M metres
# of height per metre of pass, up to MAX_LOFT_M. Shorter ones run along the grass.
LOFT_FROM_M = 15.0
LOFT_PER_M = 0.12
MAX_LOFT_M = 8.0
_PARABOLA = 4.0  # 4 s (1 - s) peaks at 1 halfway through the flight
CONTROL_RADIUS_M = 2.5


Snapshot = Keyframe


def snapshot(state: MatchState) -> Snapshot:
    """Capture the positions of every player on the pitch and the ball."""
    return state.keyframe(state.t_period)


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
        self._shown: dict[PlayerId, tuple[float, float]] = {}

    def reset(self, state: MatchState) -> None:
        """Begin a period: the base is the kick-off positions and the first frame is due."""
        self._base = snapshot(state)
        self._next_t = self._interval
        self._last = dict(self._base.players)
        self._shown = dict(self._base.players)

    def record(self, state: MatchState, emitter: EventEmitter) -> None:
        """Emit the frames due between the previous step and now, then rebase on now."""
        base = self._base
        if base is None:
            return
        current = snapshot(state)
        stops = [base, *(k for k in state.keyframes if base.t < k.t < current.t), current]
        state.keyframes.clear()
        for start, end in pairwise(stops):
            moment = _Moment.of(start, end)
            while self._next_t <= end.t:
                view = _FrameView(moment, self._next_t - start.t)
                self._emit(state, emitter, float(self._next_t), view)
                self._next_t += self._interval
        self._base = current

    def _catch_up(
        self, wanted: dict[PlayerId, tuple[float, float]]
    ) -> dict[PlayerId, tuple[float, float]]:
        """Move each shown player toward where the sim has him by at most a sprint's distance."""
        reach = MAX_SPEED_MPS * self._interval
        shown: dict[PlayerId, tuple[float, float]] = {}
        for pid, target in wanted.items():
            at = self._shown.get(pid, target)
            gap = distance_m(at[0], at[1], target[0], target[1])
            shown[pid] = target if gap <= reach else _blend(at, target, reach / gap)
        self._shown = shown
        return shown

    @staticmethod
    def _controlling(
        carrier: PlayerId | None,
        positions: dict[PlayerId, tuple[float, float]],
        ball: tuple[float, float],
    ) -> PlayerId | None:
        """The carrier, but only once he has actually reached the ball."""
        if carrier is None or carrier not in positions:
            return carrier
        spot = positions[carrier]
        return (
            carrier if distance_m(spot[0], spot[1], ball[0], ball[1]) <= CONTROL_RADIUS_M else None
        )

    def _emit(self, state: MatchState, emitter: EventEmitter, at: float, view: _FrameView) -> None:
        positions = self._catch_up(view.positions())
        rows = []
        for team in (state.home, state.away):
            for player in team.players:
                x, y = positions.get(player.player_id, (player.x, player.y))
                before = self._last.get(player.player_id, (x, y))
                speed = distance_m(before[0], before[1], x, y) / self._interval
                vx = (x - before[0]) * PITCH_LENGTH_M / self._interval
                vy = (y - before[1]) * PITCH_WIDTH_M / self._interval
                rows.append(
                    FramePlayer(
                        player_id=player.player_id,
                        x=round(clamp(x, 0.0, 1.0), PRECISION),
                        y=round(clamp(y, 0.0, 1.0), PRECISION),
                        speed_mps=round(speed, 1),
                        vx=round(vx, 1),
                        vy=round(vy, 1),
                        exhaustion=round(min(1.0, player.exhaustion), PRECISION),
                    )
                )
        self._last = positions
        ball = view.ball()
        carrier = self._controlling(view.carrier(), positions, ball)
        saved = state.t_period
        state.t_period = at
        try:
            emitter.emit(
                state,
                FrameEvent,
                Meta(),
                ball_pos_x=round(clamp(ball[0], 0.0, 1.0), PRECISION),
                ball_pos_y=round(clamp(ball[1], 0.0, 1.0), PRECISION),
                carrier_id=carrier,
                ball_height_m=round(view.ball_height(), 2),
                players=tuple(rows),
            )
        finally:
            state.t_period = saved


def _ease(share: float) -> float:
    """Slow in, quick out: the shape of a player settling into a jog."""
    return share * (2.0 - share)


@dataclass(frozen=True, slots=True)
class _Moment:
    """One step of the engine: two snapshots and how the ball and the passer move between them."""

    start: Snapshot
    end: Snapshot
    flight_s: float  # how long the ball is in the air (the whole span for a carried ball)
    ball_first: bool  # a long moment: the ball arrives first, then the wait
    carry: tuple[float, float]  # how far the passer jogs on with the ball before he plays it

    @property
    def span(self) -> float:
        """Seconds of match time the moment covers."""
        return self.end.t - self.start.t

    @property
    def passes(self) -> bool:
        """True when the ball changes hands."""
        return self.start.carrier != self.end.carrier

    @classmethod
    def of(cls, start: Snapshot, end: Snapshot) -> _Moment:
        """Plan the moment from its two ends (frames only; nothing here feeds the sim)."""
        span = end.t - start.t
        metres = distance_m(*start.ball, *end.ball)
        if start.carrier == end.carrier or span <= 0:
            return cls(start, end, span, ball_first=False, carry=(0.0, 0.0))
        flight = min(span, max(MIN_TRAVEL_S, metres / BALL_SPEED_MPS))
        long_moment = span > LONG_MOMENT_S
        hold = 0.0 if long_moment else span - flight
        reach = min(CARRY_SPEED_MPS * hold, MAX_CARRY_M, CARRY_SHARE * metres)
        share = reach / metres if metres > 0 else 0.0
        carry = ((end.ball[0] - start.ball[0]) * share, (end.ball[1] - start.ball[1]) * share)
        return cls(start, end, flight, ball_first=long_moment, carry=carry)


@dataclass(frozen=True, slots=True)
class _FrameView:
    """The picture `elapsed` seconds into a moment."""

    moment: _Moment
    elapsed: float

    @property
    def _fraction(self) -> float:
        """Share of the whole moment gone, for players walking to their places."""
        return self.elapsed / self.moment.span if self.moment.span > 0 else 1.0

    @property
    def _flown(self) -> float:
        """Share of the ball's flight done (0 while the carrier still holds it)."""
        moment = self.moment
        if not moment.passes:
            return self._fraction
        if self.elapsed >= moment.span - _EPSILON:
            return 1.0
        begins = 0.0 if moment.ball_first else moment.span - moment.flight_s
        return clamp((self.elapsed - begins) / moment.flight_s, 0.0, 1.0)

    def _jog(self) -> tuple[float, float]:
        """How far the passer has jogged on with the ball (zero once the ball has left him)."""
        moment = self.moment
        hold = moment.span - moment.flight_s
        if hold <= 0 or moment.ball_first:
            return 0.0, 0.0
        share = _ease(min(self.elapsed / hold, 1.0)) if self.elapsed <= hold else 1.0 - self._flown
        return moment.carry[0] * share, moment.carry[1] * share

    def positions(self) -> dict[PlayerId, tuple[float, float]]:
        """Return each player's interpolated position (new arrivals appear where they are)."""
        moment = self.moment
        jog = self._jog()
        out: dict[PlayerId, tuple[float, float]] = {}
        for pid, spot in moment.end.players.items():
            at = _blend(moment.start.players.get(pid, spot), spot, self._fraction)
            if moment.ball_first and pid == moment.end.carrier:
                at = _blend(moment.start.players.get(pid, spot), spot, self._flown)
            if pid == moment.start.carrier and moment.passes:
                at = (at[0] + jog[0], at[1] + jog[1])
            out[pid] = at
        return out

    def ball(self) -> tuple[float, float]:
        """Return the ball: with its carrier while held, then in flight to the next man."""
        moment = self.moment
        if not moment.passes:
            return _blend(moment.start.ball, moment.end.ball, self._fraction)
        jog = self._jog()
        held = (moment.start.ball[0] + jog[0], moment.start.ball[1] + jog[1])
        if moment.ball_first:
            held = moment.start.ball
        return _blend(held, moment.end.ball, self._flown)

    def ball_height(self) -> float:
        """Metres above the grass: zero on the ground, a parabola for a long pass in the air."""
        moment = self.moment
        flown = self._flown
        if not moment.passes or flown <= 0.0 or flown >= 1.0:
            return 0.0
        metres = distance_m(*moment.start.ball, *moment.end.ball)
        if metres <= LOFT_FROM_M:
            return 0.0
        peak = min(LOFT_PER_M * metres, MAX_LOFT_M)
        return peak * _PARABOLA * flown * (1.0 - flown)

    def carrier(self) -> PlayerId:
        """The man on the ball: the old carrier until the ball has landed, then the new one."""
        landed = self._flown >= 1.0 - _EPSILON
        return self.moment.end.carrier if landed else self.moment.start.carrier
