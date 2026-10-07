"""The AI manager: checkpoints, triggers, and carrying out a change at the next dead ball.

Each side's manager reviews the match every few minutes (sooner for a flexible one), at half-time
and after a goal or a dismissal. A review reads the assessment, weighs the candidate plans and
draws one; a change of players or mentality is made at the next stoppage (docs/design/02 section
11). Only the manager's own stream is drawn from, so swapping the AI never moves the play stream.
Deviations: no formation changes, no opponent-threat response and no half-time talk yet.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from footystreams.events.discipline import CardEvent, TacticalChangeEvent, TacticsChange
from footystreams.events.types import MatchEvent
from footystreams.sim.emit import Meta
from footystreams.sim.manager_assess import assess
from footystreams.sim.manager_plans import Plan, candidate_plans, choose_plan
from footystreams.sim.play import Play
from footystreams.sim.rng import SimRng
from footystreams.sim.side import Side
from footystreams.sim.subs import Window, can_change, make_substitution, replacement_for
from footystreams.sim.tactics_view import mentality_name, shift_mentality

SIDES: tuple[Side, Side] = ("home", "away")
DEAD_BALLS = frozenset(
    {
        "goal",
        "foul",
        "card",
        "injury",
        "offside",
        "throw_in",
        "goal_kick",
        "corner",
        "free_kick",
        "penalty",
    }
)
TRIGGERS = frozenset({"goal"})
_HALF = 0.5


@dataclass(slots=True)
class Agent:
    """One manager's private state: his stream, when he next looks, and what he has noticed."""

    rng: SimRng
    next_review_s: float = 0.0
    triggered: bool = False
    seen_difference: int = 0
    last_shift_s: float = -1e9  # elapsed_s of his latest change of mentality


class ManagerAI:
    """Both managers of a match; `after_action` and `at_halftime` are the only entry points."""

    def __init__(self, play: Play, home: SimRng, away: SimRng) -> None:
        """Start with a first checkpoint scheduled for each manager."""
        self._play = play
        self._agents = {"home": Agent(home), "away": Agent(away)}
        for side in SIDES:
            self._schedule(side)

    def after_action(self, events: Sequence[MatchEvent]) -> float:
        """Note goals and dismissals; at a stoppage let due managers review. Returns seconds."""
        if not events:
            return 0.0
        if any(self._is_trigger(event) for event in events):
            for agent in self._agents.values():
                agent.triggered = True
        if not any(event.type in DEAD_BALLS for event in events):
            return 0.0
        return sum(self._review_if_due(side) for side in SIDES)

    def at_halftime(self) -> float:
        """Let both managers review at the break (changes here do not use a window)."""
        return sum(self._review(side, Window.HALFTIME) for side in SIDES)

    @staticmethod
    def _is_trigger(event: MatchEvent) -> bool:
        if isinstance(event, CardEvent):
            return event.colour != "yellow"
        return event.type in TRIGGERS

    def _schedule(self, side: Side) -> None:
        """Set the next checkpoint: base x (slow - flexibility x flex), jittered."""
        cfg, agent = self._play.cfg.manager, self._agents[side]
        flexibility = self._play.state.team(side).sheet.manager.flexibility
        spacing = cfg.review_base_s * (cfg.review_slow - cfg.review_flexibility * flexibility)
        jitter = 1.0 + cfg.review_jitter * (agent.rng.u() - _HALF) * 2.0
        agent.next_review_s = self._play.state.elapsed_s + spacing * jitter

    def _review_if_due(self, side: Side) -> float:
        agent = self._agents[side]
        if agent.triggered or self._play.state.elapsed_s >= agent.next_review_s:
            return self._review(side, Window.PLAY)
        return 0.0

    def _review(self, side: Side, window: Window) -> float:
        play, agent = self._play, self._agents[side]
        cfg = play.cfg.manager
        team = play.state.team(side)
        agent.triggered = False
        view = assess(play.state, side, agent.rng, cfg)
        plans = candidate_plans(view, team.sheet.manager.sub_habits, agent.seen_difference, cfg)
        agent.seen_difference = view.men_difference
        self._schedule(side)
        plan = choose_plan(plans, agent.rng, cfg)
        return 0.0 if plan is None else self._carry_out(side, plan, window)

    def _carry_out(self, side: Side, plan: Plan, window: Window) -> float:
        agent = self._agents[side]
        now_s = self._play.state.elapsed_s
        if plan.rungs and now_s - agent.last_shift_s >= self._play.cfg.manager.shift_cooldown_s:
            agent.last_shift_s = now_s
            self._change_mentality(side, plan)
        return self._change_player(side, plan, window)

    def _change_mentality(self, side: Side, plan: Plan) -> None:
        team = self._play.state.team(side)
        team.view = shift_mentality(team.view, plan.rungs)
        meta = Meta(team=side, headline=f"{team.sheet.club.short_code} change mentality")
        self._play.emit.emit(
            self._play.state,
            TacticalChangeEvent,
            meta,
            changes=(TacticsChange(field="mentality", value=mentality_name(team.view)),),
        )

    def _change_player(self, side: Side, plan: Plan, window: Window) -> float:
        play = self._play
        team = play.state.team(side)
        if plan.off is None or not can_change(team, play.state.elapsed_s, window, play.cfg.manager):
            return 0.0
        on_id = replacement_for(team, plan.off)
        if on_id is None:
            return 0.0
        fit = team.sheet.squad[on_id].position_competence.get(plan.off.position, 0)
        if fit < play.cfg.manager.min_fit:
            return 0.0
        return make_substitution(play, plan.off, on_id, plan.reason, window)
