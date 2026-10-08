import pytest

from footystreams.events.open_play import OffsideEvent, PassEvent
from footystreams.events.restarts import FreeKickEvent
from footystreams.sim.actions.offside import offside_called, punish_offside
from footystreams.sim.actions.passing import PassKind
from footystreams.sim.actions.resolve_pass import resolve_pass
from footystreams.sim.config import OffsideConfig, SimConfig, merge_config
from footystreams.sim.offside import call_probability, in_offside_position, offside_line
from footystreams.sim.options import ActionKind, Option
from footystreams.sim.play import Play
from footystreams.sim.positioning import offside_ceiling, update_positions
from footystreams.sim.state import PlayerState
from tests.factories.sim_play import make_play

ON = merge_config(SimConfig(), {"offside": {"enabled": True}})


def test_offside_line__is_the_second_last_defender_in_the_attackers_frame() -> None:
    play = make_play(config=ON)
    defenders = play.state.away
    for index, player in enumerate(defenders.players):
        player.x = 0.9 - 0.05 * index  # last man 0.9 (keeper is index 0), second-last 0.85
    assert offside_line(defenders, 1) == pytest.approx(0.85)


def test_offside_line__respects_the_attack_direction() -> None:
    play = make_play(config=ON)
    home = play.state.home
    for index, player in enumerate(home.players):
        player.x = 0.1 + 0.05 * index
    assert offside_line(home, -1) == pytest.approx(1.0 - 0.15)


def test_in_offside_position__needs_to_be_beyond_the_line_and_the_ball() -> None:
    assert in_offside_position(0.9, 0.5, 0.8)
    assert not in_offside_position(0.9, 0.95, 0.8)
    assert not in_offside_position(0.7, 0.5, 0.8)


def test_call_probability__grows_with_the_referees_consistency() -> None:
    cfg = OffsideConfig()
    assert call_probability(1.0, cfg) > call_probability(0.0, cfg)
    assert call_probability(1.0, cfg) < 1.0


def _setup_offside(play: Play, receiver_x: float) -> tuple[PlayerState, PlayerState]:
    carrier = play.state.carrier
    carrier.x, carrier.y = 0.5, 0.5
    play.state.ball_x, play.state.ball_y = 0.5, 0.5
    for index, player in enumerate(play.state.away.players):
        player.x, player.y = 0.9 - 0.05 * index, 0.5
    receiver = next(p for p in play.state.home.players if p is not carrier and p.slot == 8)
    receiver.x, receiver.y = receiver_x, 0.4
    return carrier, receiver


def _pass_to(receiver: PlayerState) -> Option:
    end = (receiver.x, receiver.y)
    return Option(ActionKind.PASS, 1.0, 1.0, end, 0.0, receiver, PassKind.THROUGH, 20.0)


def test_offside_called__an_onside_receiver_is_never_flagged_and_costs_no_draw() -> None:
    play = make_play(config=ON)
    carrier, receiver = _setup_offside(play, 0.6)
    before = play.discipline.draws
    assert not offside_called(play, carrier, receiver)
    assert play.discipline.draws == before


def test_offside_called__a_receiver_beyond_the_line_costs_one_draw() -> None:
    play = make_play(config=ON)
    carrier, receiver = _setup_offside(play, 0.97)
    before = play.discipline.draws
    offside_called(play, carrier, receiver)
    assert play.discipline.draws == before + 1


def test_offside_called__flags_most_but_not_all_offside_passes() -> None:
    cfg = ON
    flagged = 0
    for seed in range(200):
        play = make_play(seed, config=cfg)
        carrier, receiver = _setup_offside(play, 0.97)
        flagged += offside_called(play, carrier, receiver)
    assert 150 < flagged < 200


def test_punish_offside__emits_the_offside_then_an_indirect_free_kick_for_the_defence() -> None:
    play = make_play(config=ON)
    receiver = play.state.home.players[8]
    receiver.x, receiver.y = 0.9, 0.3
    seconds = punish_offside(play, receiver, "mch_demo0001:00004")
    offside, kick = play.emit.events
    assert isinstance(offside, OffsideEvent)
    assert offside.caused_by == "mch_demo0001:00004"
    assert offside.player_id == receiver.player_id
    assert isinstance(kick, FreeKickEvent)
    assert (kick.kind, kick.team, kick.caused_by) == ("indirect", "away", offside.id)
    assert play.state.carrier.side == "away"
    assert seconds > 10.0


def test_resolve_pass__a_complete_pass_to_an_offside_receiver_can_be_flagged() -> None:
    cfg = merge_config(SimConfig(), {"offside": {"enabled": True, "call_base": 2.0}})
    play = make_play(config=cfg)
    _, receiver = _setup_offside(play, 0.97)
    resolve_pass(play, _pass_to(receiver))
    first, second, third = play.emit.events[:3]
    assert isinstance(first, PassEvent)
    assert first.outcome == "complete"
    assert isinstance(second, OffsideEvent)
    assert isinstance(third, FreeKickEvent)
    assert play.state.carrier.side == "away"


def test_resolve_pass__with_offside_off_nothing_is_ever_flagged() -> None:
    play = make_play(config=merge_config(SimConfig(), {"offside": {"enabled": False}}))
    _, receiver = _setup_offside(play, 0.97)
    resolve_pass(play, _pass_to(receiver))
    assert not any(isinstance(e, OffsideEvent) for e in play.emit.events)
    assert play.state.carrier is receiver


def test_positioning__with_the_rule_on_attackers_stay_behind_the_line() -> None:
    play = make_play(config=ON)
    state = play.state
    for index, player in enumerate(state.away.players):
        player.x, player.y = 0.9 - 0.04 * index, 0.5
    striker = state.home.players[10]
    striker.x = 0.5
    update_positions(state, 60.0, play.cfg.positioning, play.cfg.offside)
    line = offside_line(state.away, 1)
    assert striker.x <= line
    assert offside_ceiling(state.home, state.away, striker, play.cfg.offside) < line
