"""The match loop: sequence the moments of a match; contains no formulas.

Each moment advances the positions by the time the previous action took, lets the nearest
defender challenge, otherwise lets the carrier decide, and resolves the chosen action. Two
periods are played back to back with a kick-off, half-time and full-time event around them.
"""

from __future__ import annotations

from collections.abc import Iterator

from footystreams.domain.match import MatchSetup
from footystreams.domain.referee import Referee
from footystreams.events.base import EventBase
from footystreams.events.digest import log_digest
from footystreams.events.structure import FulltimeEvent, HalftimeEvent, KickoffEvent
from footystreams.events.summary import MatchSummaryEvent
from footystreams.events.types import MatchEvent
from footystreams.sim.actions.challenge import attempt_press_tackle
from footystreams.sim.actions.resolve_dribble import resolve_clearance, resolve_dribble
from footystreams.sim.actions.resolve_pass import resolve_pass
from footystreams.sim.actions.resolve_shot import resolve_shot
from footystreams.sim.config import SimConfig, config_hash
from footystreams.sim.config_rules import OffsideConfig
from footystreams.sim.decision import decide
from footystreams.sim.emit import EventEmitter, Meta, TeamLabel
from footystreams.sim.options import ActionKind, Option
from footystreams.sim.play import Play
from footystreams.sim.positioning import place_for_kickoff, update_positions
from footystreams.sim.pressure import pressure_on
from footystreams.sim.referee import referee_profile
from footystreams.sim.rng import SimRng
from footystreams.sim.side import Side
from footystreams.sim.state import REGULATION_PERIOD_S, MatchState, build_state
from footystreams.sim.summary import SummaryInputs, build_summary
from footystreams.sim.tables import StaticTables

PERIODS = (1, 2)
STREAM_NAMES = (
    "play",
    "discipline",
    "injury",
    "setpiece",
    "mgr_home",
    "mgr_away",
    "dayform",
    "review",
)
_RESOLVERS = {
    ActionKind.PASS: resolve_pass,
    ActionKind.DRIBBLE: resolve_dribble,
    ActionKind.SHOOT: resolve_shot,
    ActionKind.CLEAR: resolve_clearance,
}


class MatchEngine:
    """Runs one match and yields its events in order."""

    def __init__(
        self,
        setup: MatchSetup,
        seed: int,
        config: SimConfig,
        tables: StaticTables,
        referee: Referee | None = None,
    ) -> None:
        """Prepare streams, state and the emitter; no event is produced until `run`."""
        root = SimRng(seed)
        streams = {name: root.fork(name) for name in STREAM_NAMES}
        self._setup = setup
        self._seed = seed
        self._config = config
        self._state: MatchState = build_state(setup, tables, streams["dayform"])
        self._emitter = EventEmitter(setup.match_id)
        self._play = Play(
            self._state,
            streams["play"],
            config,
            self._emitter,
            streams["discipline"],
            streams["setpiece"],
            referee_profile(referee),
        )
        self._pending_move_s = 0.0

    def run(self) -> Iterator[MatchEvent]:
        """Play the whole match, yielding events as they are produced, summary last."""
        state = self._state
        for period in PERIODS:
            self._start_period(period)
            yield from self._emitter.drain()
            while state.t_period < REGULATION_PERIOD_S:
                self._step()
                yield from self._emitter.drain()
            if period == PERIODS[0]:
                self._emit_marker(
                    HalftimeEvent, score_home=state.home.score, score_away=state.away.score
                )
        self._emit_marker(FulltimeEvent, score_home=state.home.score, score_away=state.away.score)
        yield from self._emitter.drain()
        yield self._summary_event()

    def _start_period(self, period: int) -> None:
        state = self._state
        state.period, state.t_period = period, 0.0
        kicking: Side = "home" if period == PERIODS[0] else "away"
        if period != PERIODS[0]:
            state.home.attack_dir, state.away.attack_dir = -1, 1
        place_for_kickoff(state, kicking)
        state.chain += 1
        self._pending_move_s = 0.0
        self._emit_marker(KickoffEvent, period=period, team=kicking)

    def _emit_marker(
        self, event_class: type[EventBase], *, team: TeamLabel = "none", **fields: object
    ) -> None:
        self._emitter.emit(self._state, event_class, Meta(team=team), **fields)

    def _step(self) -> None:
        state, play = self._state, self._play
        if self._pending_move_s >= self._config.positioning.step_s:
            update_positions(
                state, self._pending_move_s, self._config.positioning, self._offside_rule()
            )
            self._pending_move_s = 0.0
        state.tick += 1
        pressure = pressure_on(state.carrier, state.defenders, self._config.pressure)
        challenged = attempt_press_tackle(play, pressure)
        if challenged is not None:
            duration = challenged
        else:
            option: Option = decide(state, play.rng, self._config, pressure)
            duration = _RESOLVERS[option.kind](play, option)
        state.t_period += duration
        self._pending_move_s += duration

    def _offside_rule(self) -> OffsideConfig | None:
        return self._config.offside if self._config.offside.enabled else None

    def _summary_event(self) -> MatchEvent:
        events = list(self._emitter.events)
        inputs = SummaryInputs(self._seed, config_hash(self._config), log_digest(events))
        summary = build_summary(events, self._setup, inputs)
        self._emitter.emit(self._state, MatchSummaryEvent, Meta(), summary=summary)
        return self._emitter.drain()[0]
