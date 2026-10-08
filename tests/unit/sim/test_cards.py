from dataclasses import replace

import pytest

from footystreams.domain.types import Position
from footystreams.events.discipline import CardEvent, FoulEvent
from footystreams.events.restarts import FreeKickEvent
from footystreams.sim.actions.cards import (
    KEEPER_BASE,
    CardDecision,
    decide_card,
    dismiss,
    show_card,
    yellow_threshold,
)
from footystreams.sim.actions.foul import contest_foul
from footystreams.sim.config import DisciplineConfig, SimConfig, merge_config
from footystreams.sim.decision import decide
from footystreams.sim.discipline import Contact
from footystreams.sim.referee import NEUTRAL_REFEREE
from footystreams.sim.state import Line
from tests.factories.referee import make_referee
from tests.factories.sim_play import make_play

CFG = DisciplineConfig()


def _contact(severity: float, *, dogso: bool = False) -> Contact:
    return Contact(severity, "reckless", in_box=False, denies_opportunity=dogso)


def test_yellow_threshold__card_happy_and_strict_referees_book_milder_fouls() -> None:
    lenient = replace(NEUTRAL_REFEREE, card_tendency=0.0, strictness=0.0)
    harsh = replace(NEUTRAL_REFEREE, card_tendency=1.0, strictness=1.0)
    assert yellow_threshold(harsh, CFG) < yellow_threshold(NEUTRAL_REFEREE, CFG)
    assert yellow_threshold(NEUTRAL_REFEREE, CFG) < yellow_threshold(lenient, CFG)


def test_decide_card__mild_fouls_are_not_booked_and_serious_ones_are() -> None:
    play = make_play()
    offender = play.state.away.players[3]
    assert decide_card(play, offender, _contact(0.30)) is None
    assert decide_card(play, offender, _contact(0.75)) == CardDecision("yellow", "foul")


def test_decide_card__a_booked_player_who_offends_again_gets_a_second_yellow() -> None:
    play = make_play()
    offender = play.state.away.players[3]
    offender.yellow_cards = 1
    assert decide_card(play, offender, _contact(0.75)) == CardDecision(
        "second_yellow", "second_yellow"
    )


def test_decide_card__very_severe_fouls_are_straight_reds() -> None:
    play = make_play()
    assert decide_card(play, play.state.away.players[3], _contact(0.95)) == CardDecision(
        "red", "violent_conduct"
    )


def test_decide_card__a_denied_chance_is_a_red_when_the_share_says_so() -> None:
    cfg = merge_config(SimConfig(), {"discipline": {"dogso_red_share": 1.0}})
    play = make_play(config=cfg)
    decision = decide_card(play, play.state.away.players[3], _contact(0.40, dogso=True))
    assert decision == CardDecision("red", "denying_opportunity")


def test_decide_card__no_cards_once_a_side_is_down_to_the_minimum() -> None:
    play = make_play()
    team = play.state.away
    team.players = team.players[: CFG.min_players]
    assert decide_card(play, team.players[3], _contact(0.99)) is None


def test_dismiss__removes_the_player_and_keeps_the_sent_off_list() -> None:
    play = make_play()
    team = play.state.away
    offender = team.players[4]
    dismiss(team, offender)
    assert len(team.players) == 10
    assert team.sent_off == [offender]
    assert offender not in team.players


def test_dismiss__a_sent_off_goalkeeper_is_replaced_in_goal_by_an_outfielder() -> None:
    play = make_play()
    team = play.state.away
    old_keeper = team.keeper
    dismiss(team, old_keeper)
    stand_in = team.keeper
    assert stand_in is not old_keeper
    assert stand_in.position is Position.GK
    assert stand_in.line is Line.KEEPER
    assert (stand_in.base_x, stand_in.base_y) == KEEPER_BASE


def test_show_card__yellow_is_counted_and_red_removes_the_player_and_lowers_the_men_count() -> None:
    play = make_play()
    offender = play.state.away.players[3]
    show_card(play, offender, _contact(0.75), "mch_demo0001:00001")
    card = play.emit.events[-1]
    assert isinstance(card, CardEvent)
    assert (card.colour, card.reason, card.caused_by) == ("yellow", "foul", "mch_demo0001:00001")
    assert offender.yellow_cards == 1
    assert len(play.state.away.players) == 11
    seconds = show_card(play, offender, _contact(0.95), "mch_demo0001:00002")
    assert len(play.state.away.players) == 10
    assert seconds > 15.0
    assert play.emit.events[-1].team == "away"


def test_show_card__no_card_costs_no_time_and_emits_nothing() -> None:
    play = make_play()
    assert show_card(play, play.state.away.players[3], _contact(0.1), "x") == 0.0
    assert play.emit.events == []


def test_contest_foul__a_serious_foul_gives_tackle_foul_card_then_free_kick_in_order() -> None:
    cfg = merge_config(
        SimConfig(),
        {"discipline": {"contact_base": 1000.0, "advantage_scale": 0.0, "yellow_base": 0.0}},
    )
    for seed in range(80):
        play = make_play(seed, config=cfg, referee=make_referee(strictness=1.0, card_tendency=1.0))
        carrier = play.state.carrier
        tackler = play.state.away.players[3]
        tackler.x, tackler.y = carrier.x + 0.004, carrier.y
        if contest_foul(play, tackler, carrier, None) is None:
            continue
        kinds = [type(event) for event in play.emit.events]
        assert kinds[1:] == [FoulEvent, CardEvent, FreeKickEvent]
        card = play.emit.events[2]
        assert card.caused_by == play.emit.events[1].id
        assert play.emit.events[3].ctx.men_away <= 11
        return
    pytest.fail("no foul called")


def test_play_after_a_dismissal__the_player_is_never_offered_a_pass() -> None:
    play = make_play()
    offender = play.state.away.players[3]
    show_card(play, offender, _contact(0.95), "x")
    for _ in range(40):
        play.state.carrier = play.state.away.players[5]
        option = decide(play.state, play.rng, play.cfg, 0.1)
        assert option.target is not offender
