from dataclasses import replace

import pytest

from footystreams.events.discipline import FoulEvent
from footystreams.events.open_play import TackleEvent
from footystreams.events.restarts import FreeKickEvent
from footystreams.sim.actions.foul import contest_foul, plays_advantage
from footystreams.sim.actions.free_kick import take_free_kick
from footystreams.sim.actions.setpieces import choose_free_kick_taker, restart_delay
from footystreams.sim.config import DisciplineConfig, SimConfig, merge_config
from footystreams.sim.discipline import (
    Contact,
    contact_probability,
    denies_opportunity,
    roll_contact,
    severity_label,
    severity_of,
)
from footystreams.sim.effective import Skills
from footystreams.sim.play import Play
from footystreams.sim.state import PlayerState
from footystreams.sim.tactics_view import TacticsView, build_view
from tests.factories.match import make_team_sheet
from tests.factories.referee import make_referee
from tests.factories.sim_play import make_play

CFG = DisciplineConfig(contact_base=0.45)
ALWAYS_CONTACT = merge_config(SimConfig(), {"discipline": {"contact_base": 1000.0}})


def _skills(**overrides: float) -> Skills:
    return replace(make_play().state.home.players[3].skills, **overrides)


def _view() -> TacticsView:
    return build_view(make_team_sheet())


def test_contact_probability__aggressive_dirty_poor_tacklers_foul_more() -> None:
    calm = contact_probability(
        _skills(aggression=10.0, dirtiness=10.0, tackling=90.0), _view(), derby=False, cfg=CFG
    )
    rough = contact_probability(
        _skills(aggression=90.0, dirtiness=90.0, tackling=10.0), _view(), derby=False, cfg=CFG
    )
    assert calm < rough


def test_contact_probability__derbies_raise_it_and_the_result_is_a_probability() -> None:
    plain = contact_probability(_skills(), _view(), derby=False, cfg=CFG)
    derby = contact_probability(_skills(), _view(), derby=True, cfg=CFG)
    assert derby == pytest.approx(plain * CFG.derby_factor)
    assert 0.0 <= derby <= 1.0


def test_contact_probability__an_aggressive_tackling_style_raises_it() -> None:
    aggressive = replace(_view(), tackle_aggression=1.25)
    assert contact_probability(_skills(), aggressive, derby=False, cfg=CFG) > contact_probability(
        _skills(), _view(), derby=False, cfg=CFG
    )


def test_severity_of__rises_with_the_draw_and_with_temper() -> None:
    mild = severity_of(_skills(aggression=10.0, dirtiness=10.0), 0.5, CFG)
    wild = severity_of(_skills(aggression=95.0, dirtiness=95.0), 0.5, CFG)
    assert mild < wild
    assert severity_of(_skills(), 0.1, CFG) < severity_of(_skills(), 0.9, CFG)
    assert 0.0 <= severity_of(_skills(aggression=100.0, dirtiness=100.0), 1.0, CFG) <= 1.0


@pytest.mark.parametrize(
    ("severity", "label"), [(0.1, "careless"), (0.6, "reckless"), (0.95, "violent")]
)
def test_severity_label__thresholds(severity: float, label: str) -> None:
    assert severity_label(severity, CFG) == label


def test_denies_opportunity__through_on_goal_with_only_the_keeper_ahead() -> None:
    play = make_play()
    carrier = play.state.home.players[10]
    carrier.x, carrier.y = 0.85, 0.5
    for defender in play.state.away.players:
        defender.x, defender.y = 0.2, 0.5  # all behind him in home's frame (away defends x -> 1)
    play.state.away.players[0].x = 0.99
    assert denies_opportunity(carrier, play.state.away.players, CFG, 1)
    for defender in play.state.away.players[:4]:
        defender.x = 0.95
    assert not denies_opportunity(carrier, play.state.away.players, CFG, 1)


def test_denies_opportunity__a_man_in_midfield_is_not_through() -> None:
    play = make_play()
    carrier = play.state.home.players[8]
    carrier.x = 0.4
    assert not denies_opportunity(carrier, [], CFG, 1)


def _tackle_pair(play: Play) -> tuple[PlayerState, PlayerState]:
    carrier = play.state.carrier
    tackler = play.state.away.players[3]
    tackler.x, tackler.y = carrier.x + 0.004, carrier.y
    return tackler, carrier


def test_roll_contact__no_contact_when_the_base_rate_is_zero() -> None:
    cfg = merge_config(SimConfig(), {"discipline": {"contact_base": 0.0}})
    play = make_play(config=cfg)
    tackler, carrier = _tackle_pair(play)
    assert roll_contact(play, tackler, carrier) is None


def test_roll_contact__called_fouls_report_box_and_label() -> None:
    contacts = []
    for seed in range(60):
        play = make_play(seed, config=ALWAYS_CONTACT, referee=make_referee(strictness=1.0))
        tackler, carrier = _tackle_pair(play)
        contact = roll_contact(play, tackler, carrier)
        if contact is not None:
            contacts.append(contact)
    assert contacts
    assert all(isinstance(c, Contact) and not c.in_box for c in contacts)
    assert {c.label for c in contacts} <= {"careless", "reckless", "violent"}


def test_roll_contact__in_the_box_is_flagged() -> None:
    for seed in range(60):
        play = make_play(seed, config=ALWAYS_CONTACT, referee=make_referee(strictness=1.0))
        carrier = play.state.carrier
        carrier.x, carrier.y = 0.95, 0.5
        play.state.ball_x, play.state.ball_y = 0.95, 0.5
        tackler = play.state.away.players[3]
        tackler.x, tackler.y = 0.96, 0.5
        contact = roll_contact(play, tackler, carrier)
        if contact is not None:
            assert contact.in_box
            return
    pytest.fail("no called foul")


def test_contest_foul__emits_tackle_then_foul_then_a_free_kick_for_the_fouled_side() -> None:
    cfg = merge_config(
        SimConfig(), {"discipline": {"contact_base": 1000.0, "advantage_scale": 0.0}}
    )
    for seed in range(60):
        play = make_play(seed, config=cfg, referee=make_referee(strictness=1.0))
        tackler, carrier = _tackle_pair(play)
        stoppage = contest_foul(play, tackler, carrier, "mch_demo0001:00099")
        if stoppage is None:
            continue
        tackle, foul, kick = play.emit.events
        assert isinstance(tackle, TackleEvent)
        assert tackle.outcome == "foul"
        assert tackle.caused_by == "mch_demo0001:00099"
        assert isinstance(foul, FoulEvent)
        assert foul.caused_by == tackle.id
        assert foul.fouler_id == tackler.player_id
        assert foul.fouled_id == carrier.player_id
        assert isinstance(kick, FreeKickEvent)
        assert kick.caused_by == foul.id
        assert kick.team == "home"
        assert play.state.carrier.side == "home"
        assert stoppage > 5.0
        return
    pytest.fail("no foul called")


def test_contest_foul__advantage_leaves_play_running_with_no_restart() -> None:
    cfg = merge_config(
        SimConfig(), {"discipline": {"contact_base": 1000.0, "advantage_scale": 1000.0}}
    )
    outcomes = []
    for seed in range(120):
        play = make_play(
            seed, config=cfg, referee=make_referee(strictness=1.0, advantage_tendency=1.0)
        )
        tackler, carrier = _tackle_pair(play)
        stoppage = contest_foul(play, tackler, carrier, None)
        if stoppage is not None:
            outcomes.append((stoppage, [type(e) for e in play.emit.events]))
    assert any(stoppage == 0.0 and FreeKickEvent not in kinds for stoppage, kinds in outcomes)


def test_plays_advantage__never_after_a_violent_foul_or_in_the_box() -> None:
    play = make_play(config=merge_config(SimConfig(), {"discipline": {"advantage_scale": 1000.0}}))
    violent = Contact(0.95, "violent", in_box=False, denies_opportunity=False)
    boxed = Contact(0.5, "reckless", in_box=True, denies_opportunity=False)
    assert not plays_advantage(play, violent)
    assert not plays_advantage(play, boxed)


def test_choose_free_kick_taker__prefers_the_named_taker_then_the_best_deliverer() -> None:
    play = make_play()
    team = play.state.home
    named = team.sheet.free_kick_takers[0]
    assert choose_free_kick_taker(team).player_id == named
    team.players = [player for player in team.players if player.player_id != named]
    best = max(
        (p for p in team.players if p is not team.keeper),
        key=lambda p: (p.skills.set_piece_delivery, -p.slot),
    )
    assert choose_free_kick_taker(team) is best


def test_take_free_kick__emits_the_event_and_puts_the_taker_on_the_ball() -> None:
    play = make_play()
    seconds = take_free_kick(play, "away", (0.4, 0.3), "indirect", "mch_demo0001:00005")
    event = play.emit.events[0]
    assert isinstance(event, FreeKickEvent)
    assert event.kind == "indirect"
    assert event.caused_by == "mch_demo0001:00005"
    assert play.state.carrier.side == "away"
    assert (play.state.ball_x, play.state.ball_y) == (0.4, 0.3)
    assert seconds > 10.0
    assert play.state.chain == 1


def test_restart_delay__stays_within_the_spread() -> None:
    play = make_play()
    values = [restart_delay(play, 20.0, 5.0) for _ in range(50)]
    assert all(15.0 <= value <= 25.0 for value in values)
