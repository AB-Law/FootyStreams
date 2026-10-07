"""The causal event context: momentum, intensity, significance and tags.

A `ContextTracker` folds the events of one match in order. For each event it uses only that
event and the ones before it (a "future-blind" tagger, docs/design/03 section 2.4), so a live
narrator can trust it and a replay of any prefix of the log reproduces the same context. Pure:
the simulator calls it as it emits, and tests and `verify` replay it over a finished log.
Constants are definitions, not tuning knobs: nothing in play reads the context.
"""

from __future__ import annotations

from collections import Counter, deque
from math import sqrt

from footystreams.domain.types import PlayerId
from footystreams.events.clock import match_elapsed_s
from footystreams.events.context import ContextTag
from footystreams.events.discipline import CardEvent, FoulEvent, InjuryEvent
from footystreams.events.open_play import (
    DribbleEvent,
    GoalEvent,
    InterceptionEvent,
    PassEvent,
    SaveEvent,
    ShotEvent,
    TackleEvent,
)
from footystreams.events.restarts import CornerEvent, PenaltyEvent
from footystreams.events.structure import FrameEvent
from footystreams.events.types import MatchEvent

MOMENTUM_TAU_S = 180.0  # credits fade over about three minutes
MOMENTUM_SCALE = 6.0  # home-minus-away credit that moves momentum most of the way to +-1
INTENSITY_WINDOW_S = 300
INTENSITY_PIVOT = 6.0  # weighted events in the window that make a match "medium" hot
INTENSITY_SCALE = 6.0
BIG_CHANCE_XG = 0.3
LATE_GAME_MINUTE = 75
LAST_MINUTES_MINUTE = 88
PRECISION = 4
_HALF = 0.5
_CREDIT_PASS_XT = 1.0  # a completed pass credits its threat gain
_CREDIT_SHOT_BASE = 0.03
_CREDIT_CORNER = 0.04
_CREDIT_DRIBBLE = 0.01
_CREDIT_WIN = 0.01
_CREDIT_PENALTY = 0.25
_INTENSITY_WEIGHT = {
    ShotEvent: 1.0,
    GoalEvent: 1.0,
    CornerEvent: 0.4,
    CardEvent: 0.8,
    FoulEvent: 0.3,
    TackleEvent: 0.3,
    InjuryEvent: 0.2,
}
_SIGNIFICANCE_BOOST = {
    ContextTag.EQUALISER: 0.10,
    ContextTag.GO_AHEAD_GOAL: 0.10,
    ContextTag.COMEBACK_GOAL: 0.10,
    ContextTag.HAT_TRICK: 0.10,
    ContextTag.BRACE: 0.05,
    ContextTag.BIG_CHANCE: 0.05,
    ContextTag.BIG_SAVE: 0.05,
    ContextTag.LATE_GAME: 0.05,
    ContextTag.LAST_MINUTES: 0.05,
}
_MATTERS = 0.1  # events below this significance are not boosted by the match situation
_SIGNIFICANCE_BY_TYPE = {
    "goal": 1.0,
    "penalty": 0.6,
    "card": 0.4,
    "injury": 0.35,
    "substitution": 0.2,
    "save": 0.3,
    "shot": 0.15,
    "foul": 0.1,
    "tackle": 0.08,
    "interception": 0.06,
}
_DEFAULT_SIGNIFICANCE = 0.04
_XG_SIGNIFICANCE = 2.0


def significance(event_type: str, xg: float) -> float:
    """Return how much an event matters in [0, 1]: a rule on type, lifted by shot quality."""
    base = _SIGNIFICANCE_BY_TYPE.get(event_type, _DEFAULT_SIGNIFICANCE)
    if event_type == "shot":
        base += _XG_SIGNIFICANCE * xg
    return min(1.0, max(0.0, base))


def _squash(z: float) -> float:
    """The bounded S-curve 0.5 + 0.5 z / sqrt(1 + z^2): exact on every platform."""
    return _HALF + _HALF * z / sqrt(1.0 + z * z)


class ContextTracker:
    """Annotates events with causal context, one at a time and in order."""

    def __init__(self, *, is_derby: bool = False) -> None:
        """Start a match at 0-0 with no history."""
        self._is_derby = is_derby
        self._goals = {"home": 0, "away": 0}
        self._ever_behind = {"home": False, "away": False}
        self._scorers: Counter[PlayerId] = Counter()
        self._credit = {"home": 0.0, "away": 0.0}
        self._credit_t = 0
        self._window: deque[tuple[int, float]] = deque()
        self._window_sum = 0.0
        self._shot_xg: dict[str, float] = {}
        self._penalties: set[str] = set()
        self._by_type = {
            GoalEvent: self._goal_tags,
            ShotEvent: self._shot_tags,
            SaveEvent: self._save_tags,
            CardEvent: self._card_tags,
            InjuryEvent: self._injury_tags,
        }

    def annotate(self, event: MatchEvent) -> MatchEvent:
        """Return the event with momentum, intensity, significance and tags filled in."""
        if isinstance(event, FrameEvent):
            return event
        moment = match_elapsed_s(event.clock)
        self._fade(moment)
        tags = self._tags(event)
        context = event.ctx.model_copy(
            update={
                "momentum": self._momentum(),
                "intensity": self._intensity(moment),
                "significance": self._significance(event, tags),
                "tags": self._merged(event.ctx.tags, tags),
            }
        )
        self._observe(event, moment)
        return event.model_copy(update={"ctx": context})

    def _fade(self, moment: int) -> None:
        """Let the momentum credits fade linearly over `MOMENTUM_TAU_S` (no exp, exact)."""
        elapsed = moment - self._credit_t
        if elapsed > 0:
            keep = max(0.0, 1.0 - elapsed / MOMENTUM_TAU_S)
            self._credit["home"] *= keep
            self._credit["away"] *= keep
            self._credit_t = moment

    def _momentum(self) -> float:
        difference = self._credit["home"] - self._credit["away"]
        return round(2.0 * _squash(MOMENTUM_SCALE * difference) - 1.0, PRECISION)

    def _intensity(self, moment: int) -> float:
        while self._window and self._window[0][0] < moment - INTENSITY_WINDOW_S:
            self._window_sum -= self._window.popleft()[1]
        return round(_squash((self._window_sum - INTENSITY_PIVOT) / INTENSITY_SCALE), PRECISION)

    @staticmethod
    def _merged(
        existing: tuple[ContextTag, ...], computed: set[ContextTag]
    ) -> tuple[ContextTag, ...]:
        """Keep tags the sim attached, then add computed ones in declaration order."""
        extra = [tag for tag in ContextTag if tag in computed and tag not in existing]
        return (*existing, *extra)

    @staticmethod
    def _significance(event: MatchEvent, tags: set[ContextTag]) -> float:
        base = significance(event.type, event.xg if isinstance(event, ShotEvent) else 0.0)
        if base < _MATTERS:
            return base
        boost = sum(_SIGNIFICANCE_BOOST.get(tag, 0.0) for tag in tags)
        return round(min(1.0, base + boost), PRECISION)

    def _tags(self, event: MatchEvent) -> set[ContextTag]:
        found: set[ContextTag] = set()
        self._time_tags(event, found)
        self._pitch_tags(event, found)
        handler = self._by_type.get(type(event))
        if handler is not None:
            handler(event, found)
        return found

    def _shot_tags(self, event: MatchEvent, found: set[ContextTag]) -> None:
        assert isinstance(event, ShotEvent)  # noqa: S101 - narrows the dispatch table's type
        if event.xg >= BIG_CHANCE_XG:
            found.add(ContextTag.BIG_CHANCE)
        if event.outcome == "woodwork":
            found.add(ContextTag.WOODWORK)

    def _save_tags(self, event: MatchEvent, found: set[ContextTag]) -> None:
        assert isinstance(event, SaveEvent)  # noqa: S101
        if self._shot_xg.get(event.shot_event_id, 0.0) >= BIG_CHANCE_XG:
            found.add(ContextTag.BIG_SAVE)

    @staticmethod
    def _card_tags(event: MatchEvent, found: set[ContextTag]) -> None:
        assert isinstance(event, CardEvent)  # noqa: S101
        if event.colour == "second_yellow":
            found.add(ContextTag.SECOND_YELLOW)

    @staticmethod
    def _injury_tags(event: MatchEvent, found: set[ContextTag]) -> None:
        assert isinstance(event, InjuryEvent)  # noqa: S101
        if event.apparent_severity == "looks_serious":
            found.add(ContextTag.INJURY_SCARE)

    def _time_tags(self, event: MatchEvent, found: set[ContextTag]) -> None:
        clock = event.clock
        if self._is_derby:
            found.add(ContextTag.DERBY)
        if clock.stoppage > 0:
            found.add(ContextTag.STOPPAGE_TIME)
        if clock.period == 2:  # noqa: PLR2004 - the second half
            if clock.minute >= LATE_GAME_MINUTE:
                found.add(ContextTag.LATE_GAME)
            if clock.minute >= LAST_MINUTES_MINUTE or clock.stoppage > 0:
                found.add(ContextTag.LAST_MINUTES)

    @staticmethod
    def _pitch_tags(event: MatchEvent, found: set[ContextTag]) -> None:
        if event.team == "none":
            return
        own, other = (
            (event.ctx.men_home, event.ctx.men_away)
            if event.team == "home"
            else (event.ctx.men_away, event.ctx.men_home)
        )
        if own > other:
            found.add(ContextTag.MAN_ADVANTAGE)
        elif own < other:
            found.add(ContextTag.TEN_MEN)

    def _goal_tags(self, event: MatchEvent, found: set[ContextTag]) -> None:
        assert isinstance(event, GoalEvent)  # noqa: S101
        team = event.team
        if team == "none":
            return
        own, other = self._goals[team], self._goals["away" if team == "home" else "home"]
        found.add(self._situation_tag(own, other))
        if self._ever_behind[team] and own + 1 >= other:
            found.add(ContextTag.COMEBACK_GOAL)
        if own + other == 0:
            found.add(ContextTag.OPENING_GOAL)
        scored = self._scorers[event.scorer_id] + 1
        if scored == 2:  # noqa: PLR2004 - a brace
            found.add(ContextTag.BRACE)
        elif scored == 3:  # noqa: PLR2004 - a hat-trick
            found.add(ContextTag.HAT_TRICK)
        if event.caused_by in self._penalties:
            found.add(ContextTag.PENALTY)
        if event.own_goal:
            found.add(ContextTag.OWN_GOAL)

    @staticmethod
    def _situation_tag(own: int, other: int) -> ContextTag:
        """Name what a goal does to the scoreline, given the scorer's goals and the other's."""
        if own + 1 == other:
            return ContextTag.EQUALISER
        if own == other:
            return ContextTag.GO_AHEAD_GOAL
        if own > other:
            return ContextTag.EXTENDS_LEAD
        return ContextTag.CONSOLATION_GOAL

    def _observe(self, event: MatchEvent, moment: int) -> None:
        """Fold the event into the history (after its own context was computed)."""
        weight = _INTENSITY_WEIGHT.get(type(event))
        if weight is not None:
            self._window.append((moment, weight))
            self._window_sum += weight
        self._credit_for(event)
        if isinstance(event, ShotEvent):
            self._shot_xg[event.id] = event.xg
        elif isinstance(event, PenaltyEvent):
            self._penalties.add(event.id)
        elif isinstance(event, GoalEvent) and event.team != "none":
            self._count_goal(event)

    def _count_goal(self, event: GoalEvent) -> None:
        self._goals[event.team] += 1
        self._scorers[event.scorer_id] += 1
        if self._goals["home"] < self._goals["away"]:
            self._ever_behind["home"] = True
        elif self._goals["away"] < self._goals["home"]:
            self._ever_behind["away"] = True

    def _credit_for(self, event: MatchEvent) -> None:
        team = event.team
        if team == "none":
            return
        value = 0.0
        if isinstance(event, ShotEvent):
            value = event.xg + _CREDIT_SHOT_BASE
        elif isinstance(event, PassEvent) and event.outcome == "complete":
            value = max(0.0, event.xt_gain) * _CREDIT_PASS_XT
        elif isinstance(event, CornerEvent):
            value = _CREDIT_CORNER
        elif isinstance(event, PenaltyEvent):
            value = _CREDIT_PENALTY
        elif isinstance(event, DribbleEvent) and event.outcome == "success":
            value = _CREDIT_DRIBBLE
        elif (isinstance(event, TackleEvent) and event.outcome == "won") or isinstance(
            event, InterceptionEvent
        ):
            value = _CREDIT_WIN
        self._credit[team] += value
