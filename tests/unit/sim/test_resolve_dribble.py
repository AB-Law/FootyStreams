from dataclasses import replace

import pytest

from footystreams.events.open_play import (
    ClearanceEvent,
    DribbleEvent,
    TackleEvent,
)
from footystreams.sim.actions.resolve_dribble import resolve_clearance, resolve_dribble
from footystreams.sim.decision import team_weights
from footystreams.sim.options import ActionKind, Option, generate_options
from footystreams.sim.play import Play
from tests.factories.sim_play import make_play


def _option(play: Play, kind: ActionKind, probability: float) -> Option:
    options = generate_options(play.state, 0.1, team_weights(play.state, play.cfg), play.cfg)
    chosen = next(option for option in options if option.kind is kind)
    return replace(chosen, probability=probability)


def test_resolve_dribble__success_carries_the_ball_forward_without_changing_side() -> None:
    play = make_play()
    option = _option(play, ActionKind.DRIBBLE, 1.0)
    resolve_dribble(play, option)
    event = play.emit.events[-1]
    assert isinstance(event, DribbleEvent)
    assert event.outcome == "success"
    assert (play.state.carrier.x, play.state.carrier.y) == option.end
    assert play.state.carrier.side == "home"


def test_resolve_dribble__failure_gives_the_ball_to_the_defence_with_a_tackle_when_tackled() -> (
    None
):
    seen = set()
    for seed in range(60):
        play = make_play(seed)
        resolve_dribble(play, _option(play, ActionKind.DRIBBLE, 0.0))
        assert play.state.carrier.side == "away"
        dribble = next(e for e in play.emit.events if isinstance(e, DribbleEvent))
        has_tackle = any(isinstance(e, TackleEvent) for e in play.emit.events)
        assert has_tackle == (dribble.outcome == "tackled")
        seen.add(dribble.outcome)
    assert seen == {"tackled", "lost"}


def test_resolve_clearance__emits_a_clearance_and_someone_wins_the_ball() -> None:
    play = make_play()
    option = Option(ActionKind.CLEAR, 1.0, 0.5, (0.6, 0.5), 0.9)
    resolve_clearance(play, option)
    assert isinstance(play.emit.events[0], ClearanceEvent)
    assert play.state.ball_x == pytest.approx(0.6)
