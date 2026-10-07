from dataclasses import replace

import pytest

from footystreams.events.open_play import (
    InterceptionEvent,
    PassEvent,
    TackleEvent,
)
from footystreams.sim.actions.challenge import attempt_press_tackle
from footystreams.sim.actions.resolve_pass import resolve_pass
from footystreams.sim.config import SimConfig, merge_config
from footystreams.sim.decision import team_weights
from footystreams.sim.options import ActionKind, Option, generate_options
from footystreams.sim.play import Play, action_duration, label, take_possession
from tests.factories.sim_play import make_play


def _option(play: Play, kind: ActionKind, probability: float) -> Option:
    options = generate_options(play.state, 0.1, team_weights(play.state, play.cfg), play.cfg)
    chosen = next(option for option in options if option.kind is kind)
    return replace(chosen, probability=probability)


def test_resolve_pass__completed_pass_moves_the_ball_to_the_receiver() -> None:
    play = make_play()
    option = _option(play, ActionKind.PASS, 1.0)
    passer, chain = play.state.carrier, play.state.chain
    duration = resolve_pass(play, option)
    event = play.emit.events[-1]
    assert isinstance(event, PassEvent)
    assert event.outcome == "complete"
    assert play.state.carrier is option.target
    assert play.state.assist_from is passer
    assert play.state.chain == chain
    assert duration > 0.5


def test_resolve_pass__failed_pass_always_hands_possession_to_the_other_side() -> None:
    for seed in range(40):
        play = make_play(seed)
        chain = play.state.chain
        resolve_pass(play, _option(play, ActionKind.PASS, 0.0))
        assert play.state.carrier.side == "away"
        assert play.state.chain == chain + 1
        assert play.state.assist_from is None


def test_resolve_pass__failures_cover_intercepted_and_incomplete() -> None:
    outcomes = set()
    for seed in range(80):
        play = make_play(seed)
        resolve_pass(play, _option(play, ActionKind.PASS, 0.0))
        outcomes.add(next(e for e in play.emit.events if isinstance(e, PassEvent)).outcome)
    assert {"intercepted", "incomplete"} <= outcomes <= {"intercepted", "incomplete", "out"}


def test_resolve_pass__interception_is_emitted_after_and_caused_by_the_pass() -> None:
    for seed in range(80):
        play = make_play(seed)
        resolve_pass(play, _option(play, ActionKind.PASS, 0.0))
        events = play.emit.events
        if isinstance(events[0], PassEvent) and events[0].outcome == "intercepted":
            assert isinstance(events[1], InterceptionEvent)
            assert events[1].caused_by == events[0].id
            assert events[1].player_id == play.state.carrier.player_id
            return
    pytest.fail("no interception in 80 seeds")


def test_attempt_press_tackle__nothing_happens_when_no_defender_is_close() -> None:
    play = make_play()
    for defender in play.state.away.players:
        defender.x, defender.y = 0.9, 0.9
    assert attempt_press_tackle(play, 1.0) is None
    assert play.emit.events == []


def test_attempt_press_tackle__close_defender_with_certain_attempt_resolves_a_tackle() -> None:
    cfg = merge_config(SimConfig(), {"challenge": {"attempt_rate": 1000.0, "tackle_base": 1.0}})
    play = make_play(config=cfg)
    carrier = play.state.carrier
    defender = play.state.away.players[3]
    defender.x, defender.y = carrier.x + 0.005, carrier.y
    result = attempt_press_tackle(play, 1.0)
    event = next(e for e in play.emit.events if isinstance(e, TackleEvent))
    assert event.outcome in {"won", "foul"}
    assert result is not None
    assert result > 0.0


def test_take_possession__same_side_keeps_chain_and_other_side_starts_a_new_one() -> None:
    play = make_play()
    state = play.state
    take_possession(state, state.home.players[4], 0.4, 0.4)
    assert state.chain == 0
    take_possession(state, state.away.players[4], 0.4, 0.4)
    assert state.chain == 1
    assert (state.ball_x, state.ball_y) == (0.4, 0.4)


def test_action_duration__stays_within_the_noise_band_and_uses_one_draw() -> None:
    play = make_play()
    draws = play.rng.draws
    duration = action_duration(play, 2.0)
    assert play.rng.draws == draws + 1
    assert 2.0 * 0.7 * 0.85 <= duration <= 2.0 * 1.3 * 1.15


def test_label__is_name_and_club_code() -> None:
    play = make_play()
    player = play.state.home.players[0]
    assert label(play.state.home, player.player_id) == "home0 (HOM)"
